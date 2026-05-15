"""Agent Critic — évalue la qualité de la recherche et déclenche les révisions."""

from app.agents.state import AgentState
from app.services.llm import chat_completion
from app.core.config import settings


async def critic_node(state: AgentState) -> dict:
    """Émet 'REVISION_NEEDED:' ou 'APPROVED:' dans critique pour le routage conditionnel."""
    research_block = "\n\n---\n\n".join(state["research"])

    response = await chat_completion(
        model=settings.model_fast,
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es un Critic rigoureux. Évalue si la recherche fournie est suffisante "
                    "pour répondre complètement à la tâche.\n"
                    "— Si des informations manquent, commence par 'REVISION_NEEDED:' "
                    "suivi de tes recommandations précises.\n"
                    "— Sinon, commence par 'APPROVED:' suivi d'un bref commentaire."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Tâche : {state['task']}\n\n"
                    f"Recherche produite :\n{research_block}"
                ),
            },
        ],
    )

    return {
        "critique": response,
        "messages": [{"role": "critic", "content": response}],
    }
