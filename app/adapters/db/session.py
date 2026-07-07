"""Moteur SQLAlchemy asynchrone et factory de sessions pour PostgreSQL."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.adapters.db.models import Base

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Crée toutes les tables déclarées si elles n'existent pas (appelé au démarrage)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Générateur de session — à injecter via FastAPI Depends."""
    async with AsyncSessionLocal() as session:
        yield session
