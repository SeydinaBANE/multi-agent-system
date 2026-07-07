"""Adapter LLM — implémente LLMPort via l'API OpenRouter (chat completion + embeddings)."""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings

_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLM:
    """Implémentation de LLMPort adossée à OpenRouter."""

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }

    async def chat_completion(self, model: str, messages: list[dict]) -> str:
        """Appelle l'endpoint chat/completions et retourne le contenu textuel de la réponse."""
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(
                f"{_BASE_URL}/chat/completions",
                headers=self._headers(),
                json={"model": model, "messages": messages},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def stream_completion(self, model: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Générateur async — stream les tokens depuis OpenRouter (SSE)."""
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream(
                "POST",
                f"{_BASE_URL}/chat/completions",
                headers=self._headers(),
                json={"model": model, "messages": messages, "stream": True},
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        token = chunk["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
                    except (KeyError, json.JSONDecodeError):
                        continue

    async def embed(self, text: str) -> list[float]:
        """Retourne le vecteur d'embedding (text-embedding-3-small, dim 1536) via OpenRouter."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{_BASE_URL}/embeddings",
                headers=self._headers(),
                json={"model": "openai/text-embedding-3-small", "input": text},
            )
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]
