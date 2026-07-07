"""Agent Critic — évalue la qualité de la recherche et déclenche les révisions."""
from __future__ import annotations

import time
from typing import Awaitable, Callable

from app.domain.ports import LLMPort
from app.domain.state import AgentState
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("critic")


def make_critic_node(llm: LLMPort) -> Callable[[AgentState], Awaitable[dict]]:
    """Construit le nœud Critic lié à l'implémentation LLM fournie."""

    async def critic_node(state: AgentState) -> dict:
        """Émet 'REVISION_NEEDED:' ou 'APPROVED:' dans critique pour le routage conditionnel."""
        t0 = time.perf_counter()
        research_block = "\n\n---\n\n".join(state["research"])

        response = await llm.chat_completion(
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

    return critic_node
