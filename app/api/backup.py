from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Body
from starlette.responses import StreamingResponse

from app.backup.events import EventBus
from app.backup.worker import BackupWorker


def create_backup_router(worker: BackupWorker, event_bus: EventBus, engine=None) -> APIRouter:
    router = APIRouter()

    @router.post("/pause")
    async def pause_worker():
        worker.pause()
        return {"status": "paused"}

    @router.post("/resume")
    async def resume_worker():
        worker.resume()
        return {"status": "resumed"}

    @router.get("/queue")
    async def get_queue():
        return worker.get_status()

    @router.get("/history")
    async def get_history(status: str | None = None):
        from app.db.engine import get_session
        from app.db.repository import get_articles_by_status
        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            articles = get_articles_by_status(session, status)
            return [
                {
                    "id": a.id,
                    "channel_slug": a.channel_slug,
                    "title": a.title,
                    "author": a.author,
                    "category": a.category,
                    "backup_status": a.backup_status,
                    "backup_error": a.backup_error,
                    "backed_up_at": a.backed_up_at.isoformat() if a.backed_up_at else None,
                }
                for a in articles
            ]

    @router.post("/status")
    async def get_backup_statuses(ids: list[int] = Body(...)):
        from app.db.engine import get_session
        from app.db.repository import get_article
        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            result: dict[str, str] = {}
            for article_id in ids:
                article = get_article(session, article_id)
                if article:
                    result[str(article_id)] = article.backup_status
            return result

    @router.get("/events")
    async def backup_events():
        q = event_bus.subscribe()

        async def generate():
            try:
                while True:
                    event = await q.get()
                    yield f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                event_bus.unsubscribe(q)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @router.post("/{channel_slug}/{article_id}")
    async def enqueue_backup(channel_slug: str, article_id: int, force: bool = False):
        position = await worker.enqueue(article_id, channel_slug, force=force)
        return {"status": "queued", "position": position}

    @router.delete("/{article_id}")
    async def cancel_backup(article_id: int):
        worker.cancel(article_id)
        return {"status": "cancelled"}

    return router
