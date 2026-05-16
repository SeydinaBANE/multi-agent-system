"""
Graph LangGraph — coordonne les 4 agents via un graph d'état.

Flux : planner → researcher → critic → writer
                      ↑_______________|  (REVISION_NEEDED + iter < 2)
"""
from __future__ import annotations
import json
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver  # fallback tests

from app.agents.router import classify
from app.agents.state import AgentState
from app.agents.planner import planner_node
from app.agents.researcher import researcher_node
from app.agents.critic import critic_node
from app.agents.writer import writer_node
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Conversation, Run
from app.db.session import AsyncSessionLocal
from app.services.cache import publish
from app.services.llm import stream_completion

log = get_logger("orchestrator")


def should_revise(state: AgentState) -> Literal["writer", "researcher"]:
    """Renvoie vers le Researcher si le Critic demande une révision et que le quota n'est pas atteint."""
    decision = "researcher" if "REVISION_NEEDED" in state["critique"] and state["iteration"] < 2 else "writer"
    log.info("routing", decision=decision, iteration=state["iteration"])
    return decision


def build_graph() -> StateGraph:
    """Construit le StateGraph avec les 4 nœuds et les arêtes conditionnelles."""
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("critic", critic_node)
    graph.add_node("writer", writer_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "critic")
    graph.add_conditional_edges(
        "critic",
        should_revise,
        {"writer": "writer", "researcher": "researcher"},
    )
    graph.add_edge("writer", END)

    return graph


_checkpointer = MemorySaver()  # remplacé par AsyncPostgresSaver au démarrage
_compiled_graph = None
_pg_pool = None


async def setup_checkpointer() -> None:
    """Initialise le checkpointer PostgreSQL (appelé dans le lifespan FastAPI)."""
    global _checkpointer, _compiled_graph, _pg_pool
    try:
        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        _pg_pool = AsyncConnectionPool(
            conninfo=settings.database_url_psycopg,
            max_size=10,
            kwargs={"autocommit": True, "prepare_threshold": 0},
            open=False,
        )
        await _pg_pool.open()
        checkpointer = AsyncPostgresSaver(_pg_pool)
        await checkpointer.setup()  # crée les tables de checkpointing si absentes
        _checkpointer = checkpointer
        _compiled_graph = None  # force la recompilation avec le nouveau checkpointer
        log.info("checkpointer_postgres_ready")
    except Exception as exc:
        log.warning("checkpointer_postgres_failed", error=str(exc), fallback="MemorySaver")


async def close_checkpointer() -> None:
    """Ferme le pool de connexions PostgreSQL au shutdown."""
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None


def get_graph():
    """Retourne le graph compilé (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile(checkpointer=_checkpointer)
    return _compiled_graph


def _initial_state(task: str) -> AgentState:
    """Construit l'état initial vide pour une nouvelle exécution."""
    return {
        "task": task,
        "plan": [],
        "research": [],
        "critique": "",
        "final_answer": "",
        "iteration": 0,
        "messages": [],
    }


async def run_workflow(task: str, session_id: str) -> AgentState:
    """Exécute le pipeline complet et retourne l'état final (mode batch)."""
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    return await graph.ainvoke(_initial_state(task), config=config)


async def stream_workflow(task: str, session_id: str):
    """Générateur async — stream les événements LangGraph token par token (mode WebSocket)."""
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    async for event in graph.astream_events(_initial_state(task), config=config, version="v2"):
        yield event


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


async def _persist_run(session_id: str, task: str, final_answer: str, iterations: int) -> None:
    """Persiste le run en base — appelé côté serveur pour survivre aux déconnexions client."""
    try:
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
            conversation = result.scalar_one_or_none()
            if conversation is None:
                conversation = Conversation(session_id=session_id)
                db.add(conversation)
                await db.flush()
            db.add(Run(
                conversation_id=conversation.id,
                task=task,
                final_answer=final_answer,
                iterations=iterations,
            ))
            await db.commit()
    except Exception as exc:
        log.warning("persist_run_failed", error=str(exc))


async def stream_and_publish(task: str, session_id: str) -> None:
    """Classifie la requête et publie soit un chat direct soit le pipeline complet."""
    channel = f"run:{session_id}"
    mode = await classify(task)
    await publish(channel, json.dumps({"type": "mode", "mode": mode}))

    if mode == "chat":
        await _stream_direct_chat(channel, task, session_id)
    else:
        await _stream_pipeline(channel, task, session_id)


async def _load_chat_history(session_id: str, limit: int = 10) -> list[dict]:
    """Récupère les derniers tours de conversation depuis PostgreSQL."""
    try:
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            conv_result = await db.execute(
                select(Conversation).where(Conversation.session_id == session_id)
            )
            conv = conv_result.scalar_one_or_none()
            if conv is None:
                return []
            runs_result = await db.execute(
                select(Run)
                .where(Run.conversation_id == conv.id)
                .order_by(Run.created_at.desc())
                .limit(limit)
            )
            runs = list(reversed(runs_result.scalars().all()))
            history: list[dict] = []
            for run in runs:
                if run.task:
                    history.append({"role": "user", "content": run.task})
                if run.final_answer:
                    history.append({"role": "assistant", "content": run.final_answer})
            return history
    except Exception as exc:
        log.warning("load_chat_history_failed", error=str(exc))
        return []


async def _stream_direct_chat(channel: str, task: str, session_id: str) -> None:
    """Répond directement depuis le LLM en incluant l'historique de la session."""
    history = await _load_chat_history(session_id)
    messages = [
        {"role": "system", "content": "Tu es un assistant IA utile et concis. Réponds directement."},
        *history,
        {"role": "user", "content": task},
    ]
    final_answer = ""
    try:
        async for token in stream_completion(settings.model_smart, messages):
            final_answer += token
            await publish(channel, json.dumps({"type": "token", "content": token}))
    except Exception as exc:
        await publish(channel, json.dumps({"type": "error", "detail": str(exc)}))
        return
    await _persist_run(session_id, task, final_answer, 0)
    await publish(channel, json.dumps({"type": "done", "final_answer": final_answer, "iterations": 0}))


async def _stream_pipeline(channel: str, task: str, session_id: str) -> None:
    """Exécute le workflow LangGraph complet et publie les événements."""
    final_state: AgentState | None = None
    try:
        async for event in stream_workflow(task, session_id):
            if event.get("event") == "on_chain_end":
                output = event.get("data", {}).get("output", {})
                if isinstance(output, dict) and "final_answer" in output and "iteration" in output:
                    final_state = output
            msg = _format_langgraph_event(event)
            if msg:
                await publish(channel, json.dumps(msg))
    except Exception as exc:
        await publish(channel, json.dumps({"type": "error", "detail": str(exc)}))
        return
    done: dict = {"type": "done"}
    if final_state:
        fa = final_state.get("final_answer", "")
        iters = final_state.get("iteration", 0)
        done["final_answer"] = fa
        done["iterations"] = iters
        await _persist_run(session_id, task, fa, iters)
    await publish(channel, json.dumps(done))
