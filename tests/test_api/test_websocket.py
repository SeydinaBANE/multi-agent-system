"""Tests du publisher Redis et du formateur d'événements LangGraph."""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch


# ── _format_langgraph_event ───────────────────────────────────────────────

def test_format_chain_start():
    from app.agents.orchestrator import _format_langgraph_event

    msg = _format_langgraph_event({"event": "on_chain_start", "name": "planner"})
    assert msg == {"type": "agent_start", "agent": "planner"}


def test_format_chain_end():
    from app.agents.orchestrator import _format_langgraph_event

    msg = _format_langgraph_event({"event": "on_chain_end", "name": "writer"})
    assert msg == {"type": "agent_done", "agent": "writer"}


def test_format_token_stream():
    from app.agents.orchestrator import _format_langgraph_event

    chunk = MagicMock()
    chunk.content = "Bonjour"
    msg = _format_langgraph_event({"event": "on_chat_model_stream", "data": {"chunk": chunk}})
    assert msg == {"type": "token", "content": "Bonjour"}


def test_format_empty_token_returns_none():
    from app.agents.orchestrator import _format_langgraph_event

    chunk = MagicMock()
    chunk.content = ""
    msg = _format_langgraph_event({"event": "on_chat_model_stream", "data": {"chunk": chunk}})
    assert msg is None


def test_format_unknown_event_returns_none():
    from app.agents.orchestrator import _format_langgraph_event

    msg = _format_langgraph_event({"event": "on_something_else"})
    assert msg is None


# ── stream_and_publish ────────────────────────────────────────────────────

async def fake_stream(task, session_id):
    yield {"event": "on_chain_start", "name": "planner"}
    yield {"event": "on_chain_end", "name": "planner"}
    yield {"event": "on_chain_start", "name": "writer"}
    yield {"event": "on_chain_end", "name": "writer"}


# ── Pipeline path ──────────────────────────────────────────────────────────

@patch("app.agents.orchestrator._persist_run", new_callable=AsyncMock)
@patch("app.agents.orchestrator.publish", new_callable=AsyncMock)
@patch("app.agents.orchestrator.classify", new_callable=AsyncMock, return_value="pipeline")
@patch("app.agents.orchestrator.stream_workflow", side_effect=fake_stream)
async def test_stream_and_publish_publishes_formatted_events(mock_stream, mock_classify, mock_publish, mock_persist):
    from app.agents.orchestrator import stream_and_publish

    await stream_and_publish("Explique le RAG", "session-1")

    published = [json.loads(c.args[1]) for c in mock_publish.call_args_list]
    types = [m["type"] for m in published]

    assert "mode" in types
    assert "agent_start" in types
    assert "agent_done" in types


@patch("app.agents.orchestrator._persist_run", new_callable=AsyncMock)
@patch("app.agents.orchestrator.publish", new_callable=AsyncMock)
@patch("app.agents.orchestrator.classify", new_callable=AsyncMock, return_value="pipeline")
@patch("app.agents.orchestrator.stream_workflow", side_effect=fake_stream)
async def test_stream_and_publish_always_sends_done(mock_stream, mock_classify, mock_publish, mock_persist):
    from app.agents.orchestrator import stream_and_publish

    await stream_and_publish("task", "session-2")

    published = [json.loads(c.args[1]) for c in mock_publish.call_args_list]
    assert published[-1]["type"] == "done"


@patch("app.agents.orchestrator._persist_run", new_callable=AsyncMock)
@patch("app.agents.orchestrator.publish", new_callable=AsyncMock)
@patch("app.agents.orchestrator.classify", new_callable=AsyncMock, return_value="pipeline")
@patch("app.agents.orchestrator.stream_workflow", side_effect=fake_stream)
async def test_stream_and_publish_uses_correct_channel(mock_stream, mock_classify, mock_publish, mock_persist):
    from app.agents.orchestrator import stream_and_publish

    await stream_and_publish("task", "session-xyz")

    channels = {c.args[0] for c in mock_publish.call_args_list}
    assert channels == {"run:session-xyz"}


@patch("app.agents.orchestrator._persist_run", new_callable=AsyncMock)
@patch("app.agents.orchestrator.publish", new_callable=AsyncMock)
@patch("app.agents.orchestrator.classify", new_callable=AsyncMock, return_value="pipeline")
@patch("app.agents.orchestrator.stream_workflow")
async def test_stream_and_publish_sends_error_on_exception(mock_stream, mock_classify, mock_publish, mock_persist):
    from app.agents.orchestrator import stream_and_publish

    async def failing_stream(*_):
        raise RuntimeError("LangGraph crash")
        yield  # rend la fonction async generator

    mock_stream.side_effect = failing_stream

    await stream_and_publish("task", "session-err")

    published = [json.loads(c.args[1]) for c in mock_publish.call_args_list]
    error_msgs = [m for m in published if m["type"] == "error"]
    assert len(error_msgs) == 1
    assert "LangGraph crash" in error_msgs[0]["detail"]
    # Après une erreur pipeline, le dernier message est "error" (le WS break dessus aussi)
    assert published[-1]["type"] == "error"


# ── Chat path ──────────────────────────────────────────────────────────────

@patch("app.agents.orchestrator._persist_run", new_callable=AsyncMock)
@patch("app.agents.orchestrator.publish", new_callable=AsyncMock)
@patch("app.agents.orchestrator.classify", new_callable=AsyncMock, return_value="chat")
@patch("app.agents.orchestrator.stream_completion")
async def test_stream_and_publish_chat_mode_sends_mode_event(mock_stream, mock_classify, mock_publish, mock_persist):
    from app.agents.orchestrator import stream_and_publish

    async def fake_tokens(*_):
        yield "Bonjour"
        yield " !"

    mock_stream.return_value = fake_tokens()

    await stream_and_publish("Bonjour", "session-chat")

    published = [json.loads(c.args[1]) for c in mock_publish.call_args_list]
    mode_event = next(m for m in published if m["type"] == "mode")
    assert mode_event["mode"] == "chat"


@patch("app.agents.orchestrator._persist_run", new_callable=AsyncMock)
@patch("app.agents.orchestrator.publish", new_callable=AsyncMock)
@patch("app.agents.orchestrator.classify", new_callable=AsyncMock, return_value="chat")
@patch("app.agents.orchestrator.stream_completion")
async def test_stream_and_publish_chat_streams_tokens(mock_stream, mock_classify, mock_publish, mock_persist):
    from app.agents.orchestrator import stream_and_publish

    async def fake_tokens(*_):
        yield "Bonjour"
        yield " monde"

    mock_stream.return_value = fake_tokens()

    await stream_and_publish("Bonjour", "session-chat-2")

    published = [json.loads(c.args[1]) for c in mock_publish.call_args_list]
    token_events = [m for m in published if m["type"] == "token"]
    assert len(token_events) == 2
    assert token_events[0]["content"] == "Bonjour"


@patch("app.agents.orchestrator._persist_run", new_callable=AsyncMock)
@patch("app.agents.orchestrator.publish", new_callable=AsyncMock)
@patch("app.agents.orchestrator.classify", new_callable=AsyncMock, return_value="chat")
@patch("app.agents.orchestrator.stream_completion")
async def test_stream_and_publish_chat_persists_run(mock_stream, mock_classify, mock_publish, mock_persist):
    from app.agents.orchestrator import stream_and_publish

    async def fake_tokens(*_):
        yield "Réponse"

    mock_stream.return_value = fake_tokens()

    await stream_and_publish("Question", "session-chat-3")

    mock_persist.assert_called_once_with("session-chat-3", "Question", "Réponse", 0)


# ── _load_chat_history ────────────────────────────────────────────────────

async def test_load_chat_history_unknown_session_returns_empty():
    from app.agents.orchestrator import _load_chat_history

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.agents.orchestrator.AsyncSessionLocal", return_value=mock_session_ctx):
        history = await _load_chat_history("unknown-session")

    assert history == []


async def test_load_chat_history_returns_messages():
    from app.agents.orchestrator import _load_chat_history

    fake_conv = MagicMock()
    fake_conv.id = 1

    fake_run = MagicMock()
    fake_run.task = "Bonjour"
    fake_run.final_answer = "Salut !"

    mock_db = AsyncMock()
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = fake_conv
    runs_result = MagicMock()
    runs_result.scalars.return_value.all.return_value = [fake_run]
    mock_db.execute = AsyncMock(side_effect=[conv_result, runs_result])

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.agents.orchestrator.AsyncSessionLocal", return_value=mock_session_ctx):
        history = await _load_chat_history("known-session")

    assert history == [
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Salut !"},
    ]


# ── _persist_run ──────────────────────────────────────────────────────────

async def test_persist_run_creates_conversation_and_run():
    from app.agents.orchestrator import _persist_run

    mock_db = AsyncMock()
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=conv_result)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.agents.orchestrator.AsyncSessionLocal", return_value=mock_session_ctx):
        await _persist_run("sess-1", "Tâche", "Réponse finale", 2)

    assert mock_db.add.call_count == 2  # Conversation + Run
    mock_db.commit.assert_called_once()


# ── setup_checkpointer fallback ───────────────────────────────────────────

async def test_setup_checkpointer_falls_back_to_memory_saver_on_error():
    import app.agents.orchestrator as orch
    from langgraph.checkpoint.memory import MemorySaver

    original_checkpointer = orch._checkpointer
    original_graph = orch._compiled_graph

    broken_module = MagicMock()
    broken_module.AsyncConnectionPool = MagicMock(side_effect=Exception("no psycopg"))

    with patch.dict(sys.modules, {"psycopg_pool": broken_module}):
        await orch.setup_checkpointer()

    assert isinstance(orch._checkpointer, MemorySaver)
    orch._checkpointer = original_checkpointer
    orch._compiled_graph = original_graph
