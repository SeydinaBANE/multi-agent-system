"""Fixtures partagées entre tous les tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.agents.state import AgentState
from app.db.session import get_session


def make_state(**overrides) -> AgentState:
    """Construit un AgentState minimal pour les tests, avec surcharge possible."""
    base: AgentState = {
        "task": "Explique le RAG",
        "plan": ["1. Définir le RAG", "2. Comparer au fine-tuning"],
        "research": [],
        "critique": "",
        "final_answer": "",
        "iteration": 0,
        "messages": [],
    }
    return {**base, **overrides}


def mock_db_session():
    """Session SQLAlchemy mockée — ne touche pas à la vraie base."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    # add() est synchrone dans SQLAlchemy — MagicMock évite le warning "coroutine never awaited"
    session.add = MagicMock()
    return session


@pytest_asyncio.fixture
async def client():
    """Client HTTP async branché directement sur l'app ASGI (sans réseau)."""
    async def _override_session():
        yield mock_db_session()

    app.dependency_overrides[get_session] = _override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
