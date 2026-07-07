"""Adapter checkpointer — gère le cycle de vie du checkpointer LangGraph (Postgres ou fallback mémoire)."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from app.application.container import Container
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("checkpointer")


class CheckpointerAdapter:
    """Construit/compile le graph LangGraph avec un checkpointer PostgreSQL, ou MemorySaver en fallback."""

    def __init__(self) -> None:
        self._checkpointer = MemorySaver()  # remplacé par AsyncPostgresSaver au démarrage
        self._compiled_graph = None
        self._pg_pool = None

    async def setup(self) -> None:
        """Initialise le checkpointer PostgreSQL (appelé dans le lifespan FastAPI)."""
        try:
            from psycopg_pool import AsyncConnectionPool
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            self._pg_pool = AsyncConnectionPool(
                conninfo=settings.database_url_psycopg,
                max_size=10,
                kwargs={"autocommit": True, "prepare_threshold": 0},
                open=False,
            )
            await self._pg_pool.open()
            log.debug("pg_pool_opened")
            checkpointer = AsyncPostgresSaver(self._pg_pool)
            await checkpointer.setup()  # crée les tables de checkpointing si absentes
            self._checkpointer = checkpointer
            log.info("checkpointer_postgres_ready")
        except Exception as exc:
            log.warning("checkpointer_postgres_failed", error=str(exc), fallback="MemorySaver")

    async def close(self) -> None:
        """Ferme le pool de connexions PostgreSQL au shutdown."""
        if self._pg_pool is not None:
            await self._pg_pool.close()
            self._pg_pool = None

    def get_graph(self, container: Container):
        """Retourne le graph compilé (compilation paresseuse, une seule fois)."""
        from app.agents.graph import build_graph

        if self._compiled_graph is None:
            self._compiled_graph = build_graph(container).compile(checkpointer=self._checkpointer)
        return self._compiled_graph
