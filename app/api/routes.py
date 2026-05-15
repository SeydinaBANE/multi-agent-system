"""Endpoints REST de l'API — expose POST /api/v1/run et GET /api/v1/sessions/{id}/runs."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import run_workflow
from app.db.models import Conversation, Run
from app.db.session import get_session

router = APIRouter(prefix="/api/v1", tags=["runs"])


class RunRequest(BaseModel):
    """Corps de la requête POST /run."""

    task: str
    session_id: str


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
async def run(
    request: RunRequest,
    db: AsyncSession = Depends(get_session),
) -> RunResponse:
    """Lance le pipeline multi-agents, persiste le run en base et retourne la réponse finale."""
    try:
        state = await run_workflow(request.task, request.session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Récupère ou crée la conversation liée à la session
    result = await db.execute(
        select(Conversation).where(Conversation.session_id == request.session_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        conversation = Conversation(session_id=request.session_id)
        db.add(conversation)
        await db.flush()

    db.add(Run(
        conversation_id=conversation.id,
        task=request.task,
        final_answer=state["final_answer"],
        iterations=state["iteration"],
    ))
    await db.commit()

    return RunResponse(
        session_id=request.session_id,
        final_answer=state["final_answer"],
        iterations=state["iteration"],
    )


@router.get("/sessions/{session_id}/runs", response_model=SessionHistory)
async def get_session_runs(
    session_id: str,
    db: AsyncSession = Depends(get_session),
) -> SessionHistory:
    """Retourne l'historique de tous les runs d'une session, du plus récent au plus ancien."""
    result = await db.execute(
        select(Conversation).where(Conversation.session_id == session_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' introuvable.")

    runs_result = await db.execute(
        select(Run)
        .where(Run.conversation_id == conversation.id)
        .order_by(Run.created_at.desc())
    )
    runs = runs_result.scalars().all()

    return SessionHistory(
        session_id=session_id,
        total_runs=len(runs),
        runs=[RunHistoryItem.model_validate(r) for r in runs],
    )
