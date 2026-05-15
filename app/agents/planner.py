"""Agent Planner — décompose la tâche en étapes de recherche actionnables."""

import time

from app.agents.state import AgentState
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm import chat_completion

log = get_logger("planner")


async def planner_node(state: AgentState) -> dict:
    """Produit une liste d'étapes numérotées à partir de la tâche brute."""
    t0 = time.perf_counter()
    response = await chat_completion(
        model=settings.model_fast,
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es un Planner expert. Décompose la tâche de l'utilisateur "
                    "en 3 à 5 étapes de recherche claires et actionnables. "
                    "Réponds uniquement avec une liste numérotée, une étape par ligne."
                ),
            },
            {"role": "user", "content": state["task"]},
        ],
    )

    steps = [line.strip() for line in response.strip().splitlines() if line.strip()]
    log.info("planner_done", steps=len(steps), model=settings.model_fast, duration=round(time.perf_counter() - t0, 2))

    return {
        "plan": steps,
        "messages": [{"role": "planner", "content": response}],
    }
