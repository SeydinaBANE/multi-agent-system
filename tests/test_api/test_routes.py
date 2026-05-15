"""Tests des endpoints POST /api/v1/run et GET /api/v1/sessions/{id}/runs."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import make_state


def make_run(id=1, task="Explique le RAG", final_answer="Réponse.", iterations=1):
    """Construit un objet Run mocké avec les attributs SQLAlchemy."""
    run = MagicMock()
    run.id = id
    run.task = task
    run.final_answer = final_answer
    run.iterations = iterations
    run.created_at = datetime(2024, 1, 15, 10, 0, 0)
    return run


@patch("app.api.routes.run_workflow", new_callable=AsyncMock)
async def test_run_returns_final_answer(mock_workflow, client):
    mock_workflow.return_value = make_state(
        final_answer="Le RAG combine retrieval et génération.",
        iteration=1,
    )

    response = await client.post("/api/v1/run", json={
        "task": "Explique le RAG",
        "session_id": "session-test",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["final_answer"] == "Le RAG combine retrieval et génération."
    assert data["session_id"] == "session-test"
    assert data["iterations"] == 1


@patch("app.api.routes.run_workflow", new_callable=AsyncMock)
async def test_run_returns_500_on_workflow_error(mock_workflow, client):
    mock_workflow.side_effect = RuntimeError("OpenRouter timeout")

    response = await client.post("/api/v1/run", json={
        "task": "Tâche",
        "session_id": "session-err",
    })

    assert response.status_code == 500
    assert "OpenRouter timeout" in response.json()["detail"]


@patch("app.api.routes.run_workflow", new_callable=AsyncMock)
async def test_run_missing_fields_returns_422(mock_workflow, client):
    response = await client.post("/api/v1/run", json={"task": "Tâche"})
    assert response.status_code == 422


@patch("app.api.routes.run_workflow", new_callable=AsyncMock)
async def test_run_calls_workflow_with_correct_args(mock_workflow, client):
    mock_workflow.return_value = make_state(final_answer="OK", iteration=0)

    await client.post("/api/v1/run", json={
        "task": "Ma tâche",
        "session_id": "s-42",
    })

    mock_workflow.assert_called_once_with("Ma tâche", "s-42")


# ── GET /api/v1/sessions/{session_id}/runs ────────────────────────────────

async def test_get_runs_returns_history(client):
    conv = MagicMock()
    conv.id = 1

    runs = [
        make_run(id=2, task="Tâche 2", iterations=2),
        make_run(id=1, task="Tâche 1", iterations=1),
    ]

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = runs

    from app.db.session import get_session

    async def override():
        session = AsyncMock()
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = conv
        second_result = MagicMock()
        second_result.scalars.return_value = scalars_mock
        session.execute.side_effect = [first_result, second_result]
        yield session

    from app.main import app
    app.dependency_overrides[get_session] = override

    response = await client.get("/api/v1/sessions/session-abc/runs")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session-abc"
    assert data["total_runs"] == 2
    assert data["runs"][0]["task"] == "Tâche 2"


async def test_get_runs_returns_404_for_unknown_session(client):
    from app.db.session import get_session

    async def override():
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result
        yield session

    from app.main import app
    app.dependency_overrides[get_session] = override

    response = await client.get("/api/v1/sessions/session-inconnue/runs")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "introuvable" in response.json()["detail"]


async def test_get_runs_empty_session(client):
    conv = MagicMock()
    conv.id = 99

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []

    from app.db.session import get_session

    async def override():
        session = AsyncMock()
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = conv
        second_result = MagicMock()
        second_result.scalars.return_value = scalars_mock
        session.execute.side_effect = [first_result, second_result]
        yield session

    from app.main import app
    app.dependency_overrides[get_session] = override

    response = await client.get("/api/v1/sessions/session-vide/runs")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total_runs"] == 0
    assert response.json()["runs"] == []
