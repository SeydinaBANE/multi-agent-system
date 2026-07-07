"""Endpoints REST de l'API — expose POST /api/v1/run et GET /api/v1/sessions/{id}/runs."""

import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.auth import verify_api_key
from app.api.deps import get_container, get_workflow_service
from app.application.container import Container
from app.application.workflow_service import WorkflowService
from app.core.limiter import limiter
from app.core.logging import get_logger

router = APIRouter(prefix="/api/v1", tags=["runs"])
log = get_logger("api")


class RunRequest(BaseModel):
    """Corps de la requête POST /run."""

    task: str = Field(..., min_length=1, max_length=10_000)
    session_id: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_-]+$")


class RunResponse(BaseModel):
    """Réponse retournée après exécution complète du pipeline."""

    session_id: str
    final_answer: str
    iterations: int


class RunHistoryItem(BaseModel):
    """Un run dans l'historique d'une session."""

    id: int
    task: str
    final_answer: str | None
    iterations: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionHistory(BaseModel):
    """Historique complet d'une session."""

    session_id: str
    total_runs: int
    runs: list[RunHistoryItem]


@router.post("/run", response_model=RunResponse)
@limiter.limit("20/minute")
async def run(
    request: Request,
    body: RunRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    container: Container = Depends(get_container),
    _: None = Depends(verify_api_key),
) -> RunResponse:
    """Lance le pipeline multi-agents, persiste le run en base et retourne la réponse finale."""
    t0 = time.perf_counter()
    log.info("run_start", session_id=body.session_id, task=body.task[:80])
    try:
        state = await workflow_service.run_workflow(body.task, body.session_id)
    except Exception as exc:
        log.error("run_failed", session_id=body.session_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Erreur interne")

    conversation_id = await container.repository.find_or_create_conversation(body.session_id)
    await container.repository.add_run(
        conversation_id,
        body.task,
        state["final_answer"],
        state["iterations"],
    )
    log.info("run_complete", session_id=body.session_id, iterations=state["iterations"], duration=round(time.perf_counter() - t0, 2))

    return RunResponse(
        session_id=body.session_id,
        final_answer=state["final_answer"],
        iterations=state["iterations"],
    )


@router.get("/sessions/{session_id}/runs", response_model=SessionHistory)
async def get_session_runs(
    session_id: str,
    container: Container = Depends(get_container),
    _: None = Depends(verify_api_key),
) -> SessionHistory:
    """Retourne l'historique de tous les runs d'une session, du plus récent au plus ancien."""
    runs = await container.repository.list_runs(session_id)

    if runs is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' introuvable.")

    return SessionHistory(
        session_id=session_id,
        total_runs=len(runs),
        runs=[RunHistoryItem.model_validate(r) for r in runs],
    )
