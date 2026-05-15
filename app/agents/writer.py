"""Agent Writer — rédige la réponse finale à partir des données consolidées."""

from app.agents.state import AgentState
from app.services.llm import chat_completion
from app.core.config import settings


async def writer_node(state: AgentState) -> dict:
    """Produit final_answer en synthétisant l'ensemble des résultats de recherche."""
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

    return {
        "final_answer": response,
        "messages": [{"role": "writer", "content": response}],
    }
