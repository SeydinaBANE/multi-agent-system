"""Tests des endpoints d'ingestion RAG."""

from unittest.mock import AsyncMock, patch
import uuid


@patch("app.api.documents.upsert", new_callable=AsyncMock)
async def test_ingest_one_returns_201(mock_upsert, client):
    response = await client.post("/api/v1/documents", json={
        "text": "Le RAG est efficace.",
        "id": "doc-1",
    })

    assert response.status_code == 201
    assert response.json()["id"] == "doc-1"
    assert response.json()["indexed"] is True


@patch("app.api.documents.upsert", new_callable=AsyncMock)
async def test_ingest_one_autogenerates_id(mock_upsert, client):
    response = await client.post("/api/v1/documents", json={
        "text": "Document sans id explicite.",
    })

    assert response.status_code == 201
    generated_id = response.json()["id"]
    # Vérifie que l'id auto-généré est un UUID valide
    uuid.UUID(generated_id)


@patch("app.api.documents.upsert", new_callable=AsyncMock)
async def test_ingest_one_calls_upsert(mock_upsert, client):
    await client.post("/api/v1/documents", json={"text": "Texte.", "id": "doc-x"})
    mock_upsert.assert_called_once_with("Texte.", "doc-x")


@patch("app.api.documents.upsert", new_callable=AsyncMock)
async def test_ingest_batch_returns_correct_count(mock_upsert, client):
    response = await client.post("/api/v1/documents/batch", json={
        "documents": [
            {"text": "Doc A", "id": "a"},
            {"text": "Doc B", "id": "b"},
            {"text": "Doc C", "id": "c"},
        ]
    })

    assert response.status_code == 201
    data = response.json()
    assert data["indexed"] == 3
    assert data["failed"] == 0
    assert len(data["results"]) == 3


@patch("app.api.documents.upsert", new_callable=AsyncMock)
async def test_ingest_batch_partial_failure(mock_upsert, client):
    mock_upsert.side_effect = [None, RuntimeError("Qdrant down"), None]

    response = await client.post("/api/v1/documents/batch", json={
        "documents": [
            {"text": "Doc A", "id": "a"},
            {"text": "Doc B", "id": "b"},
            {"text": "Doc C", "id": "c"},
        ]
    })

    assert response.status_code == 201
    data = response.json()
    assert data["indexed"] == 2
    assert data["failed"] == 1
    failed = [r for r in data["results"] if not r["indexed"]]
    assert failed[0]["id"] == "b"


@patch("app.api.documents.upsert", new_callable=AsyncMock)
async def test_ingest_one_upsert_error_returns_500(mock_upsert, client):
    mock_upsert.side_effect = RuntimeError("Qdrant indisponible")

    response = await client.post("/api/v1/documents", json={
        "text": "Texte.",
        "id": "doc-fail",
    })

    assert response.status_code == 500
