"""Classifie la requête : chat direct ou pipeline multi-agents."""
from __future__ import annotations

from typing import Literal

from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm import chat_completion

log = get_logger("router")

_PROMPT = """Classifie ce message utilisateur. Réponds UNIQUEMENT par "chat" ou "pipeline".

- "chat" : salutation, conversation courante, question factuelle simple, explication rapide, blague, calcul simple, définition brève
- "pipeline" : recherche approfondie, analyse de documents, rapport, rédaction longue, question nécessitant plusieurs sources, raisonnement multi-étapes

Message : {task}"""


async def classify(task: str) -> Literal["chat", "pipeline"]:
    """Retourne "chat" ou "pipeline" selon la complexité de la tâche."""
    try:
        result = await chat_completion(
            model=settings.model_fast,
            messages=[{"role": "user", "content": _PROMPT.format(task=task)}],
        )
        mode: Literal["chat", "pipeline"] = "pipeline" if "pipeline" in result.lower() else "chat"
    except Exception:
        mode = "pipeline"  # fallback sûr : le pipeline peut tout gérer
    log.info("router_decision", mode=mode, task=task[:60])
    return mode
