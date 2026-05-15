"""Point d'entrée FastAPI — déclare les routes REST, le WebSocket et le lifespan."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from app.api.documents import router as documents_router
from app.api.routes import router
from app.api.websocket import websocket_run
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db

log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await init_db()
    log.info("startup_complete")
    yield
    log.info("shutdown")


app = FastAPI(
    title="Multi-Agent System",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
app.include_router(documents_router)


@app.websocket("/ws/run")
async def ws_run(websocket: WebSocket) -> None:
    """Délègue la connexion WebSocket au handler dédié."""
    await websocket_run(websocket)


@app.get("/health", tags=["infra"])
async def health() -> dict:
    """Sonde de liveness — retourne {"status": "ok"} pour les health checks Docker."""
    return {"status": "ok"}
