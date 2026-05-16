"""Handler WebSocket — reçoit la tâche, lance le pipeline en arrière-plan et stream via Redis pub/sub."""

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.agents.orchestrator import stream_and_publish
from app.db.models import Conversation, Run
from app.db.session import AsyncSessionLocal
from app.services.cache import subscribe


async def _persist_run(session_id: str, task: str, final_answer: str, iterations: int) -> None:
    """Sauvegarde le run en base après un workflow WebSocket."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
        conversation = result.scalar_one_or_none()
        if conversation is None:
            conversation = Conversation(session_id=session_id)
            db.add(conversation)
            await db.flush()
        db.add(Run(
            conversation_id=conversation.id,
            task=task,
            final_answer=final_answer,
            iterations=iterations,
        ))
        await db.commit()


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
                if payload.get("type") == "done":
                    if "final_answer" in payload:
                        await _persist_run(
                            session_id=session_id,
                            task=task,
                            final_answer=payload["final_answer"],
                            iterations=payload.get("iterations", 0),
                        )
                    break
                if payload.get("type") == "error":
                    break
        finally:
            workflow_task.cancel()
            await pubsub.unsubscribe(channel)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
