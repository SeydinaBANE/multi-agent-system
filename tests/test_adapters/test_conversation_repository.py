"""Tests de SqlAlchemyConversationRepository."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.adapters.db.conversation_repository import SqlAlchemyConversationRepository


def _session_ctx(mock_db):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


async def test_find_or_create_conversation_creates_when_absent():
    mock_db = AsyncMock()
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=conv_result)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    def _add(obj):
        obj.id = 42

    mock_db.add = MagicMock(side_effect=_add)

    session_factory = MagicMock(return_value=_session_ctx(mock_db))
    repo = SqlAlchemyConversationRepository(session_factory)

    conversation_id = await repo.find_or_create_conversation("session-1")

    assert conversation_id == 42
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


async def test_find_or_create_conversation_returns_existing():
    existing = MagicMock()
    existing.id = 7
    mock_db = AsyncMock()
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = existing
    mock_db.execute = AsyncMock(return_value=conv_result)

    session_factory = MagicMock(return_value=_session_ctx(mock_db))
    repo = SqlAlchemyConversationRepository(session_factory)

    conversation_id = await repo.find_or_create_conversation("session-existing")

    assert conversation_id == 7


async def test_add_run_persists_row():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    session_factory = MagicMock(return_value=_session_ctx(mock_db))
    repo = SqlAlchemyConversationRepository(session_factory)

    await repo.add_run(1, "Tâche", "Réponse", 2)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


async def test_list_runs_returns_none_when_session_unknown():
    mock_db = AsyncMock()
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=conv_result)

    session_factory = MagicMock(return_value=_session_ctx(mock_db))
    repo = SqlAlchemyConversationRepository(session_factory)

    result = await repo.list_runs("unknown")

    assert result is None


async def test_list_runs_returns_run_records():
    conv = MagicMock()
    conv.id = 1
    fake_run = MagicMock()
    fake_run.id = 10
    fake_run.task = "Tâche"
    fake_run.final_answer = "Réponse"
    fake_run.iterations = 1
    fake_run.created_at = "2026-01-01"

    mock_db = AsyncMock()
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = conv
    runs_result = MagicMock()
    runs_result.scalars.return_value.all.return_value = [fake_run]
    mock_db.execute = AsyncMock(side_effect=[conv_result, runs_result])

    session_factory = MagicMock(return_value=_session_ctx(mock_db))
    repo = SqlAlchemyConversationRepository(session_factory)

    result = await repo.list_runs("session-known")

    assert len(result) == 1
    assert result[0].id == 10
    assert result[0].task == "Tâche"


async def test_load_recent_messages_returns_history():
    conv = MagicMock()
    conv.id = 1
    fake_run = MagicMock()
    fake_run.task = "Bonjour"
    fake_run.final_answer = "Salut !"

    mock_db = AsyncMock()
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = conv
    runs_result = MagicMock()
    runs_result.scalars.return_value.all.return_value = [fake_run]
    mock_db.execute = AsyncMock(side_effect=[conv_result, runs_result])

    session_factory = MagicMock(return_value=_session_ctx(mock_db))
    repo = SqlAlchemyConversationRepository(session_factory)

    history = await repo.load_recent_messages("session-known")

    assert history == [
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Salut !"},
    ]


async def test_load_recent_messages_unknown_session_returns_empty():
    mock_db = AsyncMock()
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=conv_result)

    session_factory = MagicMock(return_value=_session_ctx(mock_db))
    repo = SqlAlchemyConversationRepository(session_factory)

    history = await repo.load_recent_messages("unknown-session")

    assert history == []
