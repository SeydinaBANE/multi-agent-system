"""Handler WebSocket — reçoit la tâche, lance le pipeline en arrière-plan et stream via Redis pub/sub."""

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

from app.application.workflow_service import WorkflowService
from app.core.config import settings


async def websocket_run(websocket: WebSocket) -> None:
    """Souscrit au canal Redis de la session, démarre le pipeline en tâche de fond et forward les événements."""
    await websocket.accept()
    try:
        data = await websocket.receive_json()

        # Auth — vérifier le token si API_KEY est définie
        if settings.api_key and data.get("token") != settings.api_key:
            await websocket.send_json({"type": "error", "detail": "Unauthorized"})
            await websocket.close()
            return

        task: str | None = data.get("task")
        session_id: str | None = data.get("session_id")

        if not task or not task.strip():
            await websocket.send_json({"type": "error", "detail": "Le champ 'task' est requis."})
            return
        if not session_id:
            await websocket.send_json({"type": "error", "detail": "Le champ 'session_id' est requis."})
            return
        if len(task) > 10_000:
            await websocket.send_json({"type": "error", "detail": "La tâche est trop longue (max 10 000 chars)."})
            return

        workflow_service: WorkflowService = websocket.app.state.workflow_service
        channel = f"run:{session_id}"
        pubsub = await websocket.app.state.container.cache.subscribe(channel)

        workflow_task = asyncio.create_task(workflow_service.stream_and_publish(task, session_id))
        bg: set = websocket.app.state.background_tasks
        bg.add(workflow_task)
        workflow_task.add_done_callback(bg.discard)

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                payload = json.loads(message["data"])
                await websocket.send_json(payload)
                if payload.get("type") in ("done", "error"):
                    break
        finally:
            await pubsub.unsubscribe(channel)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "detail": "Erreur interne"})
        except Exception:
            pass
