"""Tests du publisher Redis et du formateur d'événements LangGraph."""

import json
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
