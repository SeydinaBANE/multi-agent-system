"""Handler WebSocket — reçoit la tâche, lance le pipeline en arrière-plan et stream via Redis pub/sub."""

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

from app.agents.orchestrator import stream_and_publish
from app.services.cache import subscribe


async def websocket_run(websocket: WebSocket) -> None:
    """Souscrit au canal Redis de la session, démarre le pipeline en tâche de fond et forward les événements."""
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        task: str = data["task"]
        session_id: str = data["session_id"]
        channel = f"run:{session_id}"

        pubsub = await subscribe(channel)
        # Lance le workflow en arrière-plan — il publie ses événements sur Redis
        workflow_task = asyncio.create_task(stream_and_publish(task, session_id))

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                payload = json.loads(message["data"])
                await websocket.send_json(payload)
                if payload.get("type") in ("done", "error"):
                    break
        finally:
            workflow_task.cancel()
            await pubsub.unsubscribe(channel)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
