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
        task: str | None = data.get("task")
        session_id: str | None = data.get("session_id")

        if not task or not task.strip():
            await websocket.send_json({"type": "error", "detail": "Le champ 'task' est requis."})
            return
        if not session_id:
            await websocket.send_json({"type": "error", "detail": "Le champ 'session_id' est requis."})
            return

        channel = f"run:{session_id}"
        pubsub = await subscribe(channel)

        # Lance le workflow en arrière-plan — persiste lui-même le run à la fin
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
            # Ne pas annuler workflow_task : il continue de s'exécuter et persiste le run
            # même si le client se déconnecte avant de recevoir "done".
            await pubsub.unsubscribe(channel)
            _ = workflow_task  # tâche en arrière-plan, gérée par l'event loop

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "detail": str(exc)})
        except Exception:
            pass
