"""Graph LangGraph — coordonne les 4 agents via un graph d'état.

Flux : planner → researcher → critic → writer
                      ↑_______________|  (REVISION_NEEDED + iter < 2)
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import StateGraph, END

from app.agents.critic import make_critic_node
from app.agents.planner import make_planner_node
from app.agents.researcher import make_researcher_node
from app.agents.writer import make_writer_node
from app.application.container import Container
from app.core.logging import get_logger
from app.domain.state import AgentState

log = get_logger("graph")


def should_revise(state: AgentState) -> Literal["writer", "researcher"]:
    """Renvoie vers le Researcher si le Critic demande une révision et que le quota n'est pas atteint."""
    decision = "researcher" if "REVISION_NEEDED" in state["critique"] and state["iterations"] < 2 else "writer"
    log.info("routing", decision=decision, iterations=state["iterations"])
    return decision


def build_graph(container: Container) -> StateGraph:
    """Construit le StateGraph avec les 4 nœuds et les arêtes conditionnelles."""
    graph = StateGraph(AgentState)

    graph.add_node("planner", make_planner_node(container.llm))
    graph.add_node("researcher", make_researcher_node(container.llm, container.vector_store, container.mcp_registry))
    graph.add_node("critic", make_critic_node(container.llm))
    graph.add_node("writer", make_writer_node(container.llm))

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
