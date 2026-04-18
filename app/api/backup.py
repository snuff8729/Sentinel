from __future__ import annotations

import asyncio
import json

from pathlib import Path

from fastapi import APIRouter, Body
from fastapi.responses import HTMLResponse
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

    @router.get("/detail/{article_id}")
    async def get_backup_detail(article_id: int):
        from app.db.engine import get_session
        from app.db.repository import get_article, get_downloads_for_article
        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            article = get_article(session, article_id)
            if not article:
                return {"error": "not found"}
            downloads = get_downloads_for_article(session, article_id)
            return {
                "article": {
                    "id": article.id,
                    "title": article.title,
                    "author": article.author,
                    "category": article.category,
                    "channel_slug": article.channel_slug,
                    "url": article.url,
                    "created_at": article.created_at.isoformat() if article.created_at else None,
                    "backup_status": article.backup_status,
                    "backup_error": article.backup_error,
                    "backed_up_at": article.backed_up_at.isoformat() if article.backed_up_at else None,
                },
                "downloads": [
                    {
                        "id": d.id,
                        "url": d.url,
                        "local_path": d.local_path,
                        "file_type": d.file_type,
                        "status": d.status,
                        "error": d.error,
                        "warning": d.warning,
                    }
                    for d in downloads
                ],
            }

    @router.get("/html/{article_id}")
    async def get_backup_html(article_id: int):
        data_dir = Path(worker._service._data_dir) if worker else Path("data")
        html_path = data_dir / "articles" / str(article_id) / "backup.html"
        if not html_path.exists():
            return HTMLResponse("<p>백업 HTML이 없습니다.</p>", status_code=404)
        html = html_path.read_text(encoding="utf-8")

        # 상대 경로를 절대 경로로 변환
        base_path = f"/data/articles/{article_id}"
        html = html.replace('./images/', f'{base_path}/images/')
        html = html.replace('./videos/', f'{base_path}/videos/')
        html = html.replace('./audio/', f'{base_path}/audio/')
        html = html.replace('../../emoticons/', '/data/emoticons/')

        # 기본 CSS 삽입 (프론트엔드 article-content.css와 동일)
        base_css = """<style>
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  max-width: 800px; margin: 0 auto; padding: 16px;
  font-size: 14px; line-height: 1.8; word-break: break-word;
  color: #1a1a1a; background: #fff;
}
img { max-width: 100%; height: auto; border-radius: 4px; margin: 4px 0; display: inline-block; }
img.emoticon, img.arca-emoticon {
  display: inline; width: auto; height: 100px; max-height: 100px;
  vertical-align: middle; margin: 0 2px; border-radius: 0;
}
.emoticon-wrapper, .combo_emoticon-wrapper { display: inline-block; }
video { max-width: 100%; border-radius: 4px; margin: 8px 0; }
audio { width: 100%; margin: 8px 0; }
pre { white-space: pre-wrap; word-break: break-word; font-family: inherit; margin: 0; }
p { margin: 4px 0; }
a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }
hr { border: none; border-top: 1px solid #e5e7eb; margin: 16px 0; }
blockquote { border-left: 3px solid #e5e7eb; padding-left: 12px; margin: 8px 0; color: #6b7280; }
code { background: #f3f4f6; padding: 2px 4px; border-radius: 3px; font-size: 0.9em; }
img.twemoji { display: inline; height: 1.2em; width: auto; vertical-align: middle; margin: 0 1px; border-radius: 0; }
.btn-more, .article-write-btns { display: none; }
</style>"""
        html = html.replace('<head>', f'<head>{base_css}', 1)
        if '<head>' not in html:
            html = base_css + html

        return HTMLResponse(html)

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

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/{channel_slug}/{article_id}")
    async def enqueue_backup(channel_slug: str, article_id: int, force: bool = False):
        position = await worker.enqueue(article_id, channel_slug, force=force)
        return {"status": "queued", "position": position}

    @router.delete("/{article_id}")
    async def cancel_backup(article_id: int):
        worker.cancel(article_id)
        return {"status": "cancelled"}

    return router
