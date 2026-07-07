"""Service applicatif — orchestre le graph LangGraph, la persistence et le pub/sub.

Remplace l'ancien app/agents/orchestrator.py : les internals qui touchaient
directement SQLAlchemy/Redis/LLM passent désormais par les ports du
Container injecté au constructeur.
"""
from __future__ import annotations

import json

from app.adapters.checkpointer.postgres_checkpointer import CheckpointerAdapter
from app.agents.router import make_classifier
from app.application.container import Container
from app.core.config import settings
from app.core.logging import get_logger
from app.domain.state import AgentState

log = get_logger("workflow_service")


class WorkflowService:
    """Point d'entrée applicatif utilisé par l'API (routes REST + WebSocket)."""

    def __init__(self, container: Container, checkpointer: CheckpointerAdapter) -> None:
        self._container = container
        self._checkpointer = checkpointer
        self._classify = make_classifier(container.llm)

    def _initial_state(self, task: str) -> AgentState:
        """Construit l'état initial vide pour une nouvelle exécution."""
        return {
            "task": task,
            "plan": [],
            "research": [],
            "critique": "",
            "final_answer": "",
            "iterations": 0,
            "messages": [],
        }

    async def run_workflow(self, task: str, session_id: str) -> AgentState:
        """Exécute le pipeline complet et retourne l'état final (mode batch)."""
        graph = self._checkpointer.get_graph(self._container)
        config = {"configurable": {"thread_id": session_id}}
        return await graph.ainvoke(self._initial_state(task), config=config)

    async def stream_workflow(self, task: str, session_id: str):
        """Générateur async — stream les événements LangGraph token par token (mode WebSocket)."""
        graph = self._checkpointer.get_graph(self._container)
        config = {"configurable": {"thread_id": session_id}}
        async for event in graph.astream_events(self._initial_state(task), config=config, version="v2"):
            yield event

    @staticmethod
    def _format_langgraph_event(event: dict) -> dict | None:
        """Convertit un événement LangGraph brut en message typé pour le client, ou None si ignoré."""
        event_type = event.get("event", "")

        if event_type == "on_chain_start":
            return {"type": "agent_start", "agent": event.get("name", "")}

        if event_type == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            content = chunk.content if hasattr(chunk, "content") else ""
            if content:
                return {"type": "token", "content": content}

        if event_type == "on_chain_end":
            return {"type": "agent_done", "agent": event.get("name", "")}

        return None

    async def _persist_run(self, session_id: str, task: str, final_answer: str, iterations: int) -> None:
        """Persiste le run en base — appelé côté serveur pour survivre aux déconnexions client."""
        try:
            conversation_id = await self._container.repository.find_or_create_conversation(session_id)
            await self._container.repository.add_run(conversation_id, task, final_answer, iterations)
        except Exception as exc:
            log.warning("persist_run_failed", error=str(exc))

    async def stream_and_publish(self, task: str, session_id: str) -> None:
        """Classifie la requête et publie soit un chat direct soit le pipeline complet."""
        channel = f"run:{session_id}"
        mode = await self._classify(task)
        await self._container.cache.publish(channel, json.dumps({"type": "mode", "mode": mode}))

        if mode == "chat":
            await self._stream_direct_chat(channel, task, session_id)
        else:
            await self._stream_pipeline(channel, task, session_id)

    async def _load_chat_history(self, session_id: str, limit: int = 5) -> list[dict]:
        """Récupère les derniers tours de conversation depuis PostgreSQL."""
        return await self._container.repository.load_recent_messages(session_id, limit)

    async def _stream_direct_chat(self, channel: str, task: str, session_id: str) -> None:
        """Répond directement depuis le LLM en incluant l'historique de la session."""
        history = await self._load_chat_history(session_id)
        messages = [
            {"role": "system", "content": "Tu es un assistant IA utile et concis. Réponds directement."},
            *history,
            {"role": "user", "content": task},
        ]
        final_answer = ""
        try:
            async for token in self._container.llm.stream_completion(settings.model_smart, messages):
                final_answer += token
                await self._container.cache.publish(channel, json.dumps({"type": "token", "content": token}))
        except Exception as exc:
            await self._container.cache.publish(channel, json.dumps({"type": "error", "detail": str(exc)}))
            return
        await self._persist_run(session_id, task, final_answer, 0)
        await self._container.cache.publish(channel, json.dumps({"type": "done", "final_answer": final_answer, "iterations": 0}))

    async def _stream_pipeline(self, channel: str, task: str, session_id: str) -> None:
        """Exécute le workflow LangGraph complet et publie les événements."""
        final_state: AgentState | None = None
        try:
            async for event in self.stream_workflow(task, session_id):
                if event.get("event") == "on_chain_end":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict) and "final_answer" in output and "iterations" in output:
                        final_state = output
                msg = self._format_langgraph_event(event)
                if msg:
                    await self._container.cache.publish(channel, json.dumps(msg))
        except Exception as exc:
            await self._container.cache.publish(channel, json.dumps({"type": "error", "detail": str(exc)}))
            return
        done: dict = {"type": "done"}
        if final_state:
            fa = final_state.get("final_answer", "")
            iters = final_state.get("iterations", 0)
            done["final_answer"] = fa
            done["iterations"] = iters
            await self._persist_run(session_id, task, fa, iters)
        await self._container.cache.publish(channel, json.dumps(done))
