"""Fixtures partagées entre tous les tests."""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.adapters.checkpointer.postgres_checkpointer import CheckpointerAdapter
from app.api.deps import get_container, get_workflow_service
from app.application.workflow_service import WorkflowService
from app.main import app
from app.domain.state import AgentState
from app.application.container import Container
from app.domain.ports import RunRecord


def make_state(**overrides) -> AgentState:
    """Construit un AgentState minimal pour les tests, avec surcharge possible."""
    base: AgentState = {
        "task": "Explique le RAG",
        "plan": ["1. Définir le RAG", "2. Comparer au fine-tuning"],
        "research": [],
        "critique": "",
        "final_answer": "",
        "iterations": 0,
        "messages": [],
    }
    return {**base, **overrides}


@pytest_asyncio.fixture
async def client():
    """Client HTTP async branché directement sur l'app ASGI (sans réseau).

    Le Container et le WorkflowService sont remplacés par des versions
    entièrement en mémoire (fake_container()) via dependency_overrides —
    aucun accès réseau/DB/Redis/Qdrant réel. Exposés sur `client.container`
    et `client.workflow_service` pour que les tests puissent les inspecter
    ou monkeypatcher une méthode précise.
    """
    container = fake_container()
    workflow_service = WorkflowService(container, CheckpointerAdapter())

    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_workflow_service] = lambda: workflow_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.container = container
        c.workflow_service = workflow_service
        yield c
    app.dependency_overrides.clear()


@dataclass
class FakeLLM:
    """Implémentation en mémoire de LLMPort — réponse canned, pas d'appel réseau."""

    response: str = "réponse test"

    async def chat_completion(self, model: str, messages: list[dict]) -> str:
        return self.response

    async def stream_completion(self, model: str, messages: list[dict]):
        for tok in self.response.split():
            yield tok + " "

    async def embed(self, text: str) -> list[float]:
        return [0.0] * 1536


@dataclass
class FakeVectorStore:
    """Implémentation en mémoire de VectorStorePort."""

    hits: list[str] = field(default_factory=list)
    upserted: list[tuple[str, str]] = field(default_factory=list)

    async def search(self, query: str, limit: int = 3) -> list[str]:
        return self.hits

    async def upsert(self, text: str, doc_id: str) -> None:
        self.upserted.append((text, doc_id))


@dataclass
class FakeCache:
    """Implémentation en mémoire de CachePort — enregistre les messages publiés."""

    published: list[tuple[str, str]] = field(default_factory=list)

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))

    async def subscribe(self, channel: str):
        raise NotImplementedError("subscribe n'est pas utilisé côté WorkflowService")


@dataclass
class FakeMCPRegistry:
    """Implémentation en mémoire de MCPRegistryPort."""

    results: dict[str, str] = field(default_factory=dict)

    @property
    def available(self) -> list:
        return []

    async def run_all(self, query: str) -> dict[str, str]:
        return self.results


@dataclass
class FakeConversationRepository:
    """Implémentation en mémoire de ConversationRepositoryPort."""

    seeded_runs: dict[str, list[RunRecord]] = field(default_factory=dict)
    _next_conversation_id: int = 1
    _conversations: dict[str, int] = field(default_factory=dict)
    _next_run_id: int = 1

    async def find_or_create_conversation(self, session_id: str) -> int:
        if session_id not in self._conversations:
            self._conversations[session_id] = self._next_conversation_id
            self._next_conversation_id += 1
        return self._conversations[session_id]

    async def add_run(self, conversation_id: int, task: str, final_answer: str | None, iterations: int) -> None:
        session_id = next(sid for sid, cid in self._conversations.items() if cid == conversation_id)
        record = RunRecord(
            id=self._next_run_id,
            task=task,
            final_answer=final_answer,
            iterations=iterations,
            created_at=datetime.now(timezone.utc),
        )
        self._next_run_id += 1
        self.seeded_runs.setdefault(session_id, []).append(record)

    async def list_runs(self, session_id: str) -> list[RunRecord] | None:
        if session_id not in self._conversations and session_id not in self.seeded_runs:
            return None
        return list(reversed(self.seeded_runs.get(session_id, [])))  # plus récent en premier

    async def load_recent_messages(self, session_id: str, limit: int = 5) -> list[dict]:
        history: list[dict] = []
        for run in self.seeded_runs.get(session_id, [])[-limit:]:
            if run.task:
                history.append({"role": "user", "content": run.task})
            if run.final_answer:
                history.append({"role": "assistant", "content": run.final_answer[:500]})
        return history


def fake_container(**overrides) -> Container:
    """Construit un Container entièrement en mémoire, personnalisable via overrides."""
    base = Container(
        llm=FakeLLM(),
        vector_store=FakeVectorStore(),
        cache=FakeCache(),
        mcp_registry=FakeMCPRegistry(),
        repository=FakeConversationRepository(),
    )
    return replace(base, **overrides)
