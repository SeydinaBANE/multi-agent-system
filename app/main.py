"""Point d'entrée FastAPI — déclare les routes REST, le WebSocket et le lifespan."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.agents.orchestrator import close_checkpointer, setup_checkpointer
from app.services.mcp_client import close_mcp, setup_mcp
from app.api.documents import router as documents_router
from app.api.routes import router
from app.api.websocket import websocket_run
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db
from app.services.cache import get_redis

log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.background_tasks: set = set()
    configure_logging()
    await init_db()
    await setup_checkpointer()
    setup_mcp()
    log.info("startup_complete")
    yield
    if app.state.background_tasks:
        await asyncio.gather(*app.state.background_tasks, return_exceptions=True)
    await close_checkpointer()
    await close_mcp()
    r = await get_redis()
    await r.aclose()
    log.info("shutdown")


app = FastAPI(
    title="Multi-Agent System",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(documents_router)


@app.websocket("/ws/run")
async def ws_run(websocket: WebSocket) -> None:
    """Délègue la connexion WebSocket au handler dédié."""
    await websocket_run(websocket)


@app.get("/", include_in_schema=False)
async def frontend() -> FileResponse:
    """Sert l'interface utilisateur."""
    return FileResponse(Path(__file__).parent.parent / "frontend" / "index.html")


@app.get("/health", tags=["infra"])
async def health() -> dict:
    """Sonde de liveness — retourne {"status": "ok"} pour les health checks Docker."""
    return {"status": "ok"}
