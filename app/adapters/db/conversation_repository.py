"""Adapter de persistance — implémente ConversationRepositoryPort via SQLAlchemy."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.db.models import Conversation, Run
from app.core.logging import get_logger
from app.domain.ports import RunRecord

log = get_logger("conversation_repository")


class SqlAlchemyConversationRepository:
    """Implémentation de ConversationRepositoryPort adossée à PostgreSQL (SQLAlchemy async).

    Chaque méthode ouvre sa propre session (async_sessionmaker injecté),
    ce qui reproduit exactement le comportement transactionnel de
    l'ancien orchestrator.py (chaque appel = sa propre transaction).
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def find_or_create_conversation(self, session_id: str) -> int:
        async with self._session_factory() as db:
            result = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
            conversation = result.scalar_one_or_none()
            if conversation is None:
                conversation = Conversation(session_id=session_id)
                db.add(conversation)
                await db.flush()
                await db.commit()
            return conversation.id

    async def add_run(
        self,
        conversation_id: int,
        task: str,
        final_answer: str | None,
        iterations: int,
    ) -> None:
        async with self._session_factory() as db:
            db.add(Run(
                conversation_id=conversation_id,
                task=task,
                final_answer=final_answer,
                iterations=iterations,
            ))
            await db.commit()

    async def list_runs(self, session_id: str) -> list[RunRecord] | None:
        async with self._session_factory() as db:
            result = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
            conversation = result.scalar_one_or_none()
            if conversation is None:
                return None
            runs_result = await db.execute(
                select(Run)
                .where(Run.conversation_id == conversation.id)
                .order_by(Run.created_at.desc())
            )
            return [
                RunRecord(
                    id=r.id,
                    task=r.task,
                    final_answer=r.final_answer,
                    iterations=r.iterations,
                    created_at=r.created_at,
                )
                for r in runs_result.scalars().all()
            ]

    async def load_recent_messages(self, session_id: str, limit: int = 5) -> list[dict]:
        try:
            async with self._session_factory() as db:
                conv_result = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
                conv = conv_result.scalar_one_or_none()
                if conv is None:
                    return []
                runs_result = await db.execute(
                    select(Run)
                    .where(Run.conversation_id == conv.id)
                    .order_by(Run.created_at.desc())
                    .limit(limit)
                )
                runs = list(reversed(runs_result.scalars().all()))
                history: list[dict] = []
                for run in runs:
                    if run.task:
                        history.append({"role": "user", "content": run.task})
                    if run.final_answer:
                        history.append({"role": "assistant", "content": run.final_answer[:500]})
                return history
        except Exception as exc:
            log.warning("load_chat_history_failed", error=str(exc))
            return []
