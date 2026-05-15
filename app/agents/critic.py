"""Agent Critic — évalue la qualité de la recherche et déclenche les révisions."""

import time

from app.agents.state import AgentState
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm import chat_completion

log = get_logger("critic")


async def critic_node(state: AgentState) -> dict:
    """Émet 'REVISION_NEEDED:' ou 'APPROVED:' dans critique pour le routage conditionnel."""
    t0 = time.perf_counter()
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

    decision = "REVISION_NEEDED" if "REVISION_NEEDED" in response else "APPROVED"
    log.info("critic_done", decision=decision, model=settings.model_fast, duration=round(time.perf_counter() - t0, 2))
    return {
        "critique": response,
        "messages": [{"role": "critic", "content": response}],
    }
