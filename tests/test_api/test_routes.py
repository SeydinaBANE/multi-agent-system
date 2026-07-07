"""Tests des endpoints POST /api/v1/run et GET /api/v1/sessions/{id}/runs."""

from unittest.mock import AsyncMock

from tests.conftest import make_state


async def test_run_returns_final_answer(client):
    client.workflow_service.run_workflow = AsyncMock(return_value=make_state(
        final_answer="Le RAG combine retrieval et génération.",
        iterations=1,
    ))

    response = await client.post("/api/v1/run", json={
        "task": "Explique le RAG",
        "session_id": "session-test",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["final_answer"] == "Le RAG combine retrieval et génération."
    assert data["session_id"] == "session-test"
    assert data["iterations"] == 1


async def test_run_returns_500_on_workflow_error(client):
    client.workflow_service.run_workflow = AsyncMock(side_effect=RuntimeError("OpenRouter timeout"))

    response = await client.post("/api/v1/run", json={
        "task": "Tâche",
        "session_id": "session-err",
    })

    assert response.status_code == 500
    assert response.json()["detail"] == "Erreur interne"


async def test_run_missing_fields_returns_422(client):
    response = await client.post("/api/v1/run", json={"task": "Tâche"})
    assert response.status_code == 422


async def test_run_calls_workflow_with_correct_args(client):
    client.workflow_service.run_workflow = AsyncMock(return_value=make_state(final_answer="OK", iterations=0))

    await client.post("/api/v1/run", json={
        "task": "Ma tâche",
        "session_id": "s-42",
    })

    client.workflow_service.run_workflow.assert_called_once_with("Ma tâche", "s-42")


async def test_run_persists_via_repository(client):
    client.workflow_service.run_workflow = AsyncMock(return_value=make_state(final_answer="OK", iterations=3))

    await client.post("/api/v1/run", json={
        "task": "Ma tâche",
        "session_id": "s-persist",
    })

    runs = client.container.repository.seeded_runs["s-persist"]
    assert len(runs) == 1
    assert runs[0].iterations == 3


# ── GET /api/v1/sessions/{session_id}/runs ────────────────────────────────

async def test_get_runs_returns_history(client):
    repo = client.container.repository
    conv_id = await repo.find_or_create_conversation("session-abc")
    await repo.add_run(conv_id, "Tâche 1", "Réponse 1", 1)
    await repo.add_run(conv_id, "Tâche 2", "Réponse 2", 2)

    response = await client.get("/api/v1/sessions/session-abc/runs")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session-abc"
    assert data["total_runs"] == 2
    assert data["runs"][0]["task"] == "Tâche 2"  # le plus récent en premier


async def test_get_runs_returns_404_for_unknown_session(client):
    response = await client.get("/api/v1/sessions/session-inconnue/runs")

    assert response.status_code == 404
    assert "introuvable" in response.json()["detail"]


async def test_get_runs_empty_session(client):
    await client.container.repository.find_or_create_conversation("session-vide")

    response = await client.get("/api/v1/sessions/session-vide/runs")

    assert response.status_code == 200
    assert response.json()["total_runs"] == 0
    assert response.json()["runs"] == []
