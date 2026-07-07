"""Ports (Protocol) — contrats que le domaine attend de l'infrastructure.

Le domaine (app/agents/*, app/application/*) ne dépend que de ces
protocoles, jamais des implémentations concrètes situées dans
app/adapters/*.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class LLMPort(Protocol):
    """Accès au modèle de langage (chat, streaming, embeddings)."""

    async def chat_completion(self, model: str, messages: list[dict]) -> str: ...

    def stream_completion(self, model: str, messages: list[dict]) -> AsyncGenerator[str, None]: ...

    async def embed(self, text: str) -> list[float]: ...


class VectorStorePort(Protocol):
    """Mémoire vectorielle pour la recherche sémantique RAG."""

    async def search(self, query: str, limit: int = 3) -> list[str]: ...

    async def upsert(self, text: str, doc_id: str) -> None: ...


class CachePort(Protocol):
    """Pub/sub utilisé pour le streaming des runs vers le client WebSocket."""

    async def publish(self, channel: str, message: str) -> None: ...

    async def subscribe(self, channel: str): ...


class SearchToolPort(Protocol):
    """Un outil MCP individuel (ex : recherche web)."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    def is_available(self) -> bool: ...

    async def run(self, query: str) -> str: ...


class MCPRegistryPort(Protocol):
    """Registre d'outils MCP exécutés en parallèle par le Researcher."""

    @property
    def available(self) -> list[SearchToolPort]: ...

    async def run_all(self, query: str) -> dict[str, str]: ...


@dataclass(frozen=True)
class RunRecord:
    """Représentation domaine d'un run persisté — jamais une ligne ORM."""

    id: int
    task: str
    final_answer: str | None
    iterations: int
    created_at: datetime


class ConversationRepositoryPort(Protocol):
    """Persistance des conversations et de leurs runs."""

    async def find_or_create_conversation(self, session_id: str) -> int: ...

    async def add_run(
        self,
        conversation_id: int,
        task: str,
        final_answer: str | None,
        iterations: int,
    ) -> None: ...

    async def list_runs(self, session_id: str) -> list[RunRecord] | None: ...

    async def load_recent_messages(self, session_id: str, limit: int = 5) -> list[dict]: ...
