"""Endpoints d'ingestion RAG — texte brut, fichier (PDF/DOCX/TXT) et URL."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.document_parser import parse_docx, parse_pdf, parse_txt, parse_url
from app.services.vector_store import upsert

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

ALLOWED_MIME: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
}


class DocumentIn(BaseModel):
    text: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class DocumentOut(BaseModel):
    id: str
    indexed: bool
    chars: int = 0


class BatchIn(BaseModel):
    documents: list[DocumentIn]


class BatchOut(BaseModel):
    indexed: int
    failed: int
    results: list[DocumentOut]


class UrlIn(BaseModel):
    url: str
    id: str | None = Field(default=None)


@router.post("", response_model=DocumentOut, status_code=201)
async def ingest_one(doc: DocumentIn) -> DocumentOut:
    """Indexe un document texte dans Qdrant."""
    try:
        await upsert(doc.text, doc.id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return DocumentOut(id=doc.id, indexed=True, chars=len(doc.text))


@router.post("/batch", response_model=BatchOut, status_code=201)
async def ingest_batch(body: BatchIn) -> BatchOut:
    """Indexe plusieurs documents en lot."""
    results: list[DocumentOut] = []
    failed = 0
    for doc in body.documents:
        try:
            await upsert(doc.text, doc.id)
            results.append(DocumentOut(id=doc.id, indexed=True, chars=len(doc.text)))
        except Exception:
            results.append(DocumentOut(id=doc.id, indexed=False))
            failed += 1
    return BatchOut(indexed=len(results) - failed, failed=failed, results=results)


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def ingest_file(
    file: UploadFile = File(...),
    doc_id: str | None = Form(default=None),
) -> DocumentOut:
    """Indexe un fichier PDF, DOCX ou TXT dans Qdrant."""
    content_type = (file.content_type or "").split(";")[0].strip()
    ext = ALLOWED_MIME.get(content_type)
    if ext is None:
        raise HTTPException(
            status_code=415,
            detail=f"Type non supporté : {content_type}. Acceptés : PDF, DOCX, TXT.",
        )
    raw = await file.read()
    try:
        if ext == "pdf":
            text = await parse_pdf(raw)
        elif ext == "docx":
            text = await parse_docx(raw)
        else:
            text = parse_txt(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Erreur d'extraction : {exc}")
    if not text.strip():
        raise HTTPException(status_code=422, detail="Aucun texte extrait du fichier.")
    final_id = doc_id or str(uuid.uuid4())
    try:
        await upsert(text, final_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return DocumentOut(id=final_id, indexed=True, chars=len(text))


@router.post("/url", response_model=DocumentOut, status_code=201)
async def ingest_url(body: UrlIn) -> DocumentOut:
    """Scrape une page web et l'indexe dans Qdrant."""
    try:
        text = await parse_url(body.url)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Erreur de scraping : {exc}")
    if not text.strip():
        raise HTTPException(status_code=422, detail="Aucun texte extrait de l'URL.")
    final_id = body.id or str(uuid.uuid4())
    try:
        await upsert(text, final_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return DocumentOut(id=final_id, indexed=True, chars=len(text))
