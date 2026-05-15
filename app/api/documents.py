"""Endpoints d'ingestion RAG — indexe des documents dans Qdrant."""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.vector_store import upsert

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


class DocumentIn(BaseModel):
    """Document à indexer."""

    text: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class DocumentOut(BaseModel):
    """Confirmation d'indexation."""

    id: str
    indexed: bool


class BatchIn(BaseModel):
    """Liste de documents à indexer en une seule requête."""

    documents: list[DocumentIn]


class BatchOut(BaseModel):
    """Résultat de l'indexation par lot."""

    indexed: int
    failed: int
    results: list[DocumentOut]


@router.post("", response_model=DocumentOut, status_code=201)
async def ingest_one(doc: DocumentIn) -> DocumentOut:
    """Indexe un document dans Qdrant et retourne son identifiant."""
    try:
        await upsert(doc.text, doc.id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return DocumentOut(id=doc.id, indexed=True)


@router.post("/batch", response_model=BatchOut, status_code=201)
async def ingest_batch(body: BatchIn) -> BatchOut:
    """Indexe plusieurs documents en parallèle et retourne le bilan."""
    results: list[DocumentOut] = []
    failed = 0

    for doc in body.documents:
        try:
            await upsert(doc.text, doc.id)
            results.append(DocumentOut(id=doc.id, indexed=True))
        except Exception:
            results.append(DocumentOut(id=doc.id, indexed=False))
            failed += 1

    return BatchOut(indexed=len(results) - failed, failed=failed, results=results)
