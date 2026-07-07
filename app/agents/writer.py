"""Agent Writer — rédige la réponse finale à partir des données consolidées."""
from __future__ import annotations

import time
from typing import Awaitable, Callable

from app.domain.ports import LLMPort
from app.domain.state import AgentState
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("writer")


def make_writer_node(llm: LLMPort) -> Callable[[AgentState], Awaitable[dict]]:
    """Construit le nœud Writer lié à l'implémentation LLM fournie."""

    async def writer_node(state: AgentState) -> dict:
        """Produit final_answer en synthétisant l'ensemble des résultats de recherche."""
        t0 = time.perf_counter()
        research_block = "\n\n---\n\n".join(state["research"])

        response = await llm.chat_completion(
            model=settings.model_smart,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es un Writer expert. Rédige une réponse finale claire, "
                        "structurée et exhaustive en français, en t'appuyant uniquement "
                        "sur les données de recherche fournies."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Tâche : {state['task']}\n\n"
                        f"Données de recherche :\n{research_block}"
                    ),
                },
            ],
        )

        log.info("writer_done", model=settings.model_smart, duration=round(time.perf_counter() - t0, 2))
        return {
            "final_answer": response,
            "messages": [{"role": "writer", "content": response}],
        }

    return writer_node
