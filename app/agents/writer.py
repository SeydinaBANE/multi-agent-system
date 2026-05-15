"""Agent Writer — rédige la réponse finale à partir des données consolidées."""

import time

from app.agents.state import AgentState
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm import chat_completion

log = get_logger("writer")


async def writer_node(state: AgentState) -> dict:
    """Produit final_answer en synthétisant l'ensemble des résultats de recherche."""
    t0 = time.perf_counter()
    research_block = "\n\n---\n\n".join(state["research"])

    response = await chat_completion(
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
