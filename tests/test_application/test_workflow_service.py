"""Tests de WorkflowService — orchestration du graph, persistence et pub/sub via fakes."""

import json

from app.adapters.checkpointer.postgres_checkpointer import CheckpointerAdapter
from app.application.workflow_service import WorkflowService
from tests.conftest import FakeCache, FakeConversationRepository, FakeLLM, fake_container


def _make_service(**overrides) -> WorkflowService:
    return WorkflowService(fake_container(**overrides), CheckpointerAdapter())


# ── _format_langgraph_event ───────────────────────────────────────────────

def test_format_chain_start():
    msg = WorkflowService._format_langgraph_event({"event": "on_chain_start", "name": "planner"})
    assert msg == {"type": "agent_start", "agent": "planner"}


def test_format_chain_end():
    msg = WorkflowService._format_langgraph_event({"event": "on_chain_end", "name": "writer"})
    assert msg == {"type": "agent_done", "agent": "writer"}


def test_format_unknown_event_returns_none():
    msg = WorkflowService._format_langgraph_event({"event": "on_something_else"})
    assert msg is None


# ── run_workflow / graph intégration avec fakes ───────────────────────────

async def test_run_workflow_returns_final_state():
    service = _make_service(llm=FakeLLM(response="APPROVED: réponse finale."))

    result = await service.run_workflow("Explique le RAG", "session-graph")

    assert result["final_answer"] == "APPROVED: réponse finale."
    assert result["iterations"] == 1


# ── _persist_run / _load_chat_history délèguent au repository ────────────

async def test_persist_run_delegates_to_repository():
    repo = FakeConversationRepository()
    service = _make_service(repository=repo)

    await service._persist_run("session-1", "Tâche", "Réponse finale", 2)

    runs = repo.seeded_runs["session-1"]
    assert len(runs) == 1
    assert runs[0].task == "Tâche"
    assert runs[0].final_answer == "Réponse finale"
    assert runs[0].iterations == 2


async def test_load_chat_history_delegates_to_repository():
    repo = FakeConversationRepository()
    conv_id = await repo.find_or_create_conversation("session-2")
    await repo.add_run(conv_id, "Bonjour", "Salut !", 0)
    service = _make_service(repository=repo)

    history = await service._load_chat_history("session-2")

    assert history == [
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Salut !"},
    ]


async def test_load_chat_history_unknown_session_returns_empty():
    service = _make_service(repository=FakeConversationRepository())

    history = await service._load_chat_history("unknown-session")

    assert history == []


# ── stream_and_publish : mode chat ────────────────────────────────────────

async def test_stream_and_publish_chat_mode_streams_tokens_and_persists():
    cache = FakeCache()
    repo = FakeConversationRepository()
    service = _make_service(llm=FakeLLM(response="chat"), cache=cache, repository=repo)

    await service.stream_and_publish("Bonjour", "session-chat")

    published = [json.loads(msg) for _, msg in cache.published]
    types = [m["type"] for m in published]
    assert types[0] == "mode"
    assert published[0]["mode"] == "chat"
    assert "token" in types
    assert types[-1] == "done"
    assert repo.seeded_runs["session-chat"][0].iterations == 0


# ── stream_and_publish : mode pipeline ────────────────────────────────────

async def test_stream_and_publish_pipeline_mode_runs_graph_and_persists():
    cache = FakeCache()
    repo = FakeConversationRepository()
    service = _make_service(llm=FakeLLM(response="pipeline: réponse complète."), cache=cache, repository=repo)

    await service.stream_and_publish("Analyse approfondie", "session-pipeline")

    published = [json.loads(msg) for _, msg in cache.published]
    types = [m["type"] for m in published]
    assert types[0] == "mode"
    assert published[0]["mode"] == "pipeline"
    assert types[-1] == "done"
    assert "session-pipeline" in repo.seeded_runs


async def test_stream_and_publish_uses_correct_channel():
    cache = FakeCache()
    service = _make_service(llm=FakeLLM(response="chat"), cache=cache)

    await service.stream_and_publish("task", "session-xyz")

    channels = {channel for channel, _ in cache.published}
    assert channels == {"run:session-xyz"}
