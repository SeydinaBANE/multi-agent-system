"""Wrapper asynchrone pour l'API OpenRouter (chat completion + embeddings)."""

import httpx
from app.core.config import settings

_BASE_URL = "https://openrouter.ai/api/v1"


def _headers() -> dict:
    """Construit les headers d'authentification pour chaque requête OpenRouter."""
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }


async def chat_completion(model: str, messages: list[dict]) -> str:
    """Appelle l'endpoint chat/completions et retourne le contenu textuel de la réponse."""
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(
            f"{_BASE_URL}/chat/completions",
            headers=_headers(),
            json={"model": model, "messages": messages},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def embed(text: str) -> list[float]:
    """Retourne le vecteur d'embedding (text-embedding-3-small, dim 1536) via OpenRouter."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{_BASE_URL}/embeddings",
            headers=_headers(),
            json={"model": "openai/text-embedding-3-small", "input": text},
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]
