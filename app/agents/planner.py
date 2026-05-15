"""Agent Planner — décompose la tâche en étapes de recherche actionnables."""

from app.agents.state import AgentState
from app.services.llm import chat_completion
from app.core.config import settings


async def planner_node(state: AgentState) -> dict:
    """Produit une liste d'étapes numérotées à partir de la tâche brute."""
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

    return {
        "plan": steps,
        "messages": [{"role": "planner", "content": response}],
    }
