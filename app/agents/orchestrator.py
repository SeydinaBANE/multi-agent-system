"""
Graph LangGraph — coordonne les 4 agents via un graph d'état.

Flux : planner → researcher → critic → writer
                      ↑_______________|  (REVISION_NEEDED + iter < 2)
"""
from __future__ import annotations
import json
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import AgentState
from app.agents.planner import planner_node
from app.agents.researcher import researcher_node
from app.agents.critic import critic_node
from app.agents.writer import writer_node
from app.core.logging import get_logger
from app.services.cache import publish

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


_checkpointer = MemorySaver()
_compiled_graph = None


def get_graph():
    """Retourne le graph compilé (singleton) avec checkpointer MemorySaver."""
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


async def stream_and_publish(task: str, session_id: str) -> None:
    """Exécute le workflow et publie chaque événement formaté sur le canal Redis de la session."""
    channel = f"run:{session_id}"
    try:
        async for event in stream_workflow(task, session_id):
            msg = _format_langgraph_event(event)
            if msg:
                await publish(channel, json.dumps(msg))
    except Exception as exc:
        await publish(channel, json.dumps({"type": "error", "detail": str(exc)}))
    finally:
        await publish(channel, json.dumps({"type": "done"}))
