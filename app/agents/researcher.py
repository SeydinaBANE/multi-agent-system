"""Agent Researcher — collecte des informations via RAG (Qdrant), MCP et LLM."""

import asyncio
import time

from app.agents.state import AgentState
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm import chat_completion
from app.services.mcp_client import get_registry
from app.services.vector_store import search

log = get_logger("researcher")


async def researcher_node(state: AgentState) -> dict:
    """Enrichit research[] en combinant la mémoire vectorielle et le LLM."""
    t0 = time.perf_counter()
    log.info("researcher_start", iterations=state["iterations"] + 1)

    rag_hits, mcp_results = await asyncio.gather(
        search(state["task"], limit=3),
        get_registry().run_all(state["task"]),
    )

    rag_block = "\n".join(rag_hits) if rag_hits else "Aucun contexte RAG disponible."
    mcp_block = (
        "\n\n".join(f"[{name}]\n{content}" for name, content in mcp_results.items())
        if mcp_results else ""
    )

    plan_block = "\n".join(state["plan"])
    critique = state["critique"]
    critique_block = f"\nFeedback Critic à intégrer :\n{critique}" if critique else ""
    web_block = f"\n\nContexte web :\n{mcp_block}" if mcp_block else ""

    response = await chat_completion(
        model=settings.model_default,
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es un Researcher expert. Collecte et synthétise des informations "
                    "pertinentes pour répondre à la tâche."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Tâche : {state['task']}\n\n"
                    f"Plan :\n{plan_block}\n\n"
                    f"Contexte RAG :\n{rag_block}"
                    f"{web_block}"
                    f"{critique_block}"
                ),
            },
        ],
    )

    log.info(
        "researcher_done",
        rag_hits=len(rag_hits),
        mcp_tools=list(mcp_results.keys()),
        model=settings.model_default,
        duration=round(time.perf_counter() - t0, 2),
    )
    return {
        "research": state["research"] + [response],
        "iterations": state["iterations"] + 1,
        "messages": [{"role": "researcher", "content": response}],
    }
