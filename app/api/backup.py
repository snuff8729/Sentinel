from __future__ import annotations

import asyncio
import json

from pathlib import Path

from fastapi import APIRouter, Body, UploadFile, File, Form
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
                    "analysis_status": a.analysis_status,
                    "analysis_error": a.analysis_error,
                    "download_complete": a.download_complete,
                }
                for a in articles
            ]

    @router.post("/status")
    async def get_backup_statuses(ids: list[int] = Body(...)):
        from app.db.engine import get_session
        from app.db.repository import get_article
        from app.db.models import VersionGroup
        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            result: dict[str, dict] = {}
            for article_id in ids:
                article = get_article(session, article_id)
                if article:
                    group_name = None
                    if article.version_group_id:
                        group = session.get(VersionGroup, article.version_group_id)
                        group_name = group.name if group else None
                    result[str(article_id)] = {
                        "status": article.backup_status,
                        "group_name": group_name,
                        "group_id": article.version_group_id,
                    }
            return result

    @router.get("/detail/{article_id}")
    async def get_backup_detail(article_id: int):
        from app.db.engine import get_session
        from app.db.repository import get_article, get_downloads_for_article, get_links_for_article
        from app.db.models import Article, ArticleFile, ArticleVersion
        from sqlmodel import select
        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            article = get_article(session, article_id)
            if not article:
                return {"error": "not found"}
            downloads = get_downloads_for_article(session, article_id)
            links = get_links_for_article(session, article_id)

            # 자유 업로드 파일
            files_stmt = select(ArticleFile).where(ArticleFile.article_id == article_id)
            files = session.exec(files_stmt).all()

            # 버전 관계
            versions_stmt = select(ArticleVersion).where(
                (ArticleVersion.article_id == article_id) | (ArticleVersion.related_article_id == article_id)
            )
            versions = session.exec(versions_stmt).all()

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
                    "analysis_status": article.analysis_status,
                    "analysis_error": article.analysis_error,
                    "version_group_id": article.version_group_id,
                    "version_label": article.version_label,
                    "download_complete": article.download_complete,
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
                "links": [
                    {
                        "id": l.id,
                        "url": l.url,
                        "type": l.link_type,
                        "label": l.label,
                        "download_status": l.download_status,
                        "download_path": l.download_path,
                        "download_error": l.download_error,
                        "source_article_id": l.source_article_id,
                    }
                    for l in links
                ],
                "files": [
                    {
                        "id": f.id,
                        "filename": f.filename,
                        "local_path": f.local_path,
                        "size": f.size,
                        "note": f.note,
                    }
                    for f in files
                ],
                "versions": [
                    {
                        "id": v.id,
                        "article_id": v.article_id,
                        "related_article_id": v.related_article_id,
                        "relation": v.relation,
                        "confidence": v.confidence,
                        "llm_reason": v.llm_reason,
                        # 상대방 게시글 제목
                        "related_title": (
                            session.get(Article, v.related_article_id if v.article_id == article_id else v.article_id)
                        ).title if session.get(Article, v.related_article_id if v.article_id == article_id else v.article_id) else "",
                        "related_id": v.related_article_id if v.article_id == article_id else v.article_id,
                    }
                    for v in versions
                ],
            }

    @router.post("/upload/{article_id}")
    async def upload_file(article_id: int, file: UploadFile = File(...), link_id: int | None = Form(None)):
        """수동 다운로드한 파일을 업로드. link_id가 있으면 해당 링크의 download_status를 업데이트."""
        data_dir = Path(worker._service._data_dir) if worker else Path("data")
        save_dir = data_dir / "articles" / str(article_id) / "downloads"
        save_dir.mkdir(parents=True, exist_ok=True)

        filename = file.filename or "uploaded_file"
        save_path = save_dir / filename
        content = await file.read()
        save_path.write_bytes(content)

        local_path = f"articles/{article_id}/downloads/{filename}"
        size_kb = len(content) / 1024

        # link_id가 있으면 DB 업데이트
        if link_id:
            from app.db.engine import get_session
            from app.db.models import ArticleLink
            _engine = engine or worker._service._engine
            with get_session(_engine) as session:
                link = session.get(ArticleLink, link_id)
                if link:
                    link.download_status = "completed"
                    link.download_path = local_path
                    link.download_error = None
                    session.add(link)
                    session.commit()

        # 전체 완료 체크
        _engine = engine or worker._service._engine
        from app.db.engine import get_session as _gs
        from app.db.repository import get_links_for_article as _gl
        with _gs(_engine) as session:
            all_links = _gl(session, article_id)
            dl_links = [l for l in all_links if l.link_type == "download"]
            if dl_links and all(l.download_status == "completed" for l in dl_links):
                from app.db.models import Article as _A
                art = session.get(_A, article_id)
                if art:
                    art.download_complete = True
                    session.add(art)
                    session.commit()

        return {
            "status": "uploaded",
            "filename": filename,
            "local_path": local_path,
            "size_kb": round(size_kb, 1),
        }

    @router.post("/upload-free/{article_id}")
    async def upload_free_file(article_id: int, file: UploadFile = File(...), note: str = Form("")):
        """링크와 관계없는 자유 파일 업로드."""
        from app.db.engine import get_session
        from app.db.models import ArticleFile

        data_dir = Path(worker._service._data_dir) if worker else Path("data")
        save_dir = data_dir / "articles" / str(article_id) / "downloads"
        save_dir.mkdir(parents=True, exist_ok=True)

        filename = file.filename or "uploaded_file"
        save_path = save_dir / filename
        content = await file.read()
        save_path.write_bytes(content)

        local_path = f"articles/{article_id}/downloads/{filename}"

        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            af = ArticleFile(
                article_id=article_id,
                filename=filename,
                local_path=local_path,
                size=len(content),
                note=note or None,
            )
            session.add(af)
            session.commit()

        return {"status": "uploaded", "filename": filename, "size_kb": round(len(content) / 1024, 1)}

    @router.put("/file/{file_id}")
    async def update_free_file(file_id: int, body: dict = Body(...)):
        """첨부 파일 alias/note 수정."""
        from app.db.engine import get_session
        from app.db.models import ArticleFile
        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            af = session.get(ArticleFile, file_id)
            if not af:
                return {"error": "not found"}
            if "filename" in body:
                af.filename = body["filename"]
            if "note" in body:
                af.note = body["note"] or None
            session.add(af)
            session.commit()
        return {"status": "updated"}

    @router.delete("/file/{file_id}")
    async def delete_free_file(file_id: int):
        """자유 업로드 파일 삭제."""
        from app.db.engine import get_session
        from app.db.models import ArticleFile

        _engine = engine or worker._service._engine
        data_dir = Path(worker._service._data_dir) if worker else Path("data")

        with get_session(_engine) as session:
            af = session.get(ArticleFile, file_id)
            if not af:
                return {"error": "not found"}
            # 파일 삭제
            file_path = data_dir / af.local_path
            if file_path.exists():
                file_path.unlink()
            session.delete(af)
            session.commit()

        return {"status": "deleted"}

    @router.post("/complete-download/{article_id}")
    async def mark_download_complete(article_id: int):
        """수동으로 외부 다운로드 완료 처리."""
        from app.db.engine import get_session
        from app.db.models import Article
        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            article = session.get(Article, article_id)
            if not article:
                return {"error": "not found"}
            article.download_complete = True
            session.add(article)
            session.commit()
        return {"status": "completed"}

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

        # 기본 CSS 삽입
        base_css = """<style>
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  max-width: 800px; margin: 0 auto; padding: 16px;
  font-size: 14px; line-height: 1.8; word-break: break-word;
  color: #1a1a1a; background: #fff;
}

/* === 헤더 === */
.article-head { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e5e7eb; }
.article-head .title { font-size: 20px; font-weight: 700; margin-bottom: 8px; }
.article-head .category-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 12px; font-weight: 500; background: #e8f5e9; color: #2e7d32; margin-right: 6px;
}
.article-head .info-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.article-head .member-info { display: flex; align-items: center; gap: 8px; }
.article-head .member-info .avatar img { width: 28px; height: 28px; border-radius: 50%; }
.article-head .user-info a { color: #1a1a1a; font-weight: 500; text-decoration: none; }
.article-head .user-icon { display: none; }
.article-head .zero-at-one-space { display: none; }
.article-head .article-info { display: flex; align-items: center; gap: 4px; font-size: 13px; color: #6b7280; }
.article-head .article-info .head { color: #9ca3af; }
.article-head .article-info .body { font-weight: 500; color: #374151; }
.article-head .article-info .sep { display: inline-block; width: 1px; height: 12px; background: #e5e7eb; margin: 0 4px; }
.article-head .ion-android-star { display: none; }

/* === 본문 === */
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

/* === 댓글 === */
.article-comment { margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; }
.article-comment > .title { font-size: 16px; font-weight: 700; margin-bottom: 12px; }
.list-area > .comment-wrapper { border-bottom: 1px solid #e5e7eb; }
.comment-wrapper { }
.comment-item { padding: 10px 0; }
.comment-item .content { }
.comment-item .info-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; font-size: 13px; }
.comment-item .user-info a { color: #1a1a1a; font-weight: 500; text-decoration: none; }
.comment-item .user-info.author a { color: #2563eb; }
.comment-item .user-icon { display: none; }
.comment-item .zero-at-one-space { display: none; }
.comment-item .avatar img { width: 24px; height: 24px; border-radius: 50%; }
.comment-item .right { font-size: 12px; color: #9ca3af; }
.comment-item .right a { color: #9ca3af; }
.comment-item .message { font-size: 14px; }
.comment-item .message .text pre { font-family: inherit; }

/* 대댓글 */
.comment-wrapper > .comment-wrapper {
  margin-left: 32px; padding-left: 12px; border-left: 2px solid #e5e7eb;
}
.comment-item .ion-android-arrow-dropup-circle { font-size: 12px; color: #9ca3af; margin-right: 4px; }

/* === 숨김 === */
.btn-more, .article-write-btns, .reply-link, [href*="reports/submit"] { display: none; }
.btn-arca-article-write, .reply-form, #commentForm { display: none; }
.sep:empty { display: none; }
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
