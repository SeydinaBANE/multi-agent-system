"""Endpoints d'ingestion RAG — texte brut, fichier (PDF/DOCX/TXT) et URL."""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.api.auth import verify_api_key
from app.core.limiter import limiter
from app.services.document_parser import parse_docx, parse_pdf, parse_txt, parse_url
from app.services.vector_store import upsert

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

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
@limiter.limit("30/minute")
async def ingest_one(
    request: Request,
    doc: DocumentIn,
    _: None = Depends(verify_api_key),
) -> DocumentOut:
    """Indexe un document texte dans Qdrant."""
    try:
        await upsert(doc.text, doc.id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erreur interne")
    return DocumentOut(id=doc.id, indexed=True, chars=len(doc.text))


@router.post("/batch", response_model=BatchOut, status_code=201)
@limiter.limit("10/minute")
async def ingest_batch(
    request: Request,
    body: BatchIn,
    _: None = Depends(verify_api_key),
) -> BatchOut:
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
@limiter.limit("20/minute")
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    doc_id: str | None = Form(default=None),
    _: None = Depends(verify_api_key),
) -> DocumentOut:
    """Indexe un fichier PDF, DOCX ou TXT dans Qdrant."""
    content_type = (file.content_type or "").split(";")[0].strip()
    ext = ALLOWED_MIME.get(content_type)
    if ext is None:
        raise HTTPException(
            status_code=415,
            detail=f"Type non supporté : {content_type}. Acceptés : PDF, DOCX, TXT.",
        )
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = file.file.read(65536)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_UPLOAD_SIZE:
            raise HTTPException(413, "Fichier trop volumineux (max 50 MB).")
        chunks.append(chunk)
    raw = b"".join(chunks)
    try:
        if ext == "pdf":
            text = await parse_pdf(raw)
        elif ext == "docx":
            text = await parse_docx(raw)
        else:
            text = await parse_txt(raw)
    except Exception:
        raise HTTPException(status_code=422, detail="Erreur d'extraction du fichier.")
    if not text.strip():
        raise HTTPException(status_code=422, detail="Aucun texte extrait du fichier.")
    final_id = doc_id or str(uuid.uuid4())
    try:
        await upsert(text, final_id)
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur interne")
    return DocumentOut(id=final_id, indexed=True, chars=len(text))


@router.post("/url", response_model=DocumentOut, status_code=201)
@limiter.limit("20/minute")
async def ingest_url(
    request: Request,
    body: UrlIn,
    _: None = Depends(verify_api_key),
) -> DocumentOut:
    """Scrape une page web et l'indexe dans Qdrant."""
    try:
        text = await parse_url(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=422, detail="Erreur de scraping.")
    if not text.strip():
        raise HTTPException(status_code=422, detail="Aucun texte extrait de l'URL.")
    final_id = body.id or str(uuid.uuid4())
    try:
        await upsert(text, final_id)
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur interne")
    return DocumentOut(id=final_id, indexed=True, chars=len(text))
