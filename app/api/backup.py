from __future__ import annotations

import asyncio
import json
import math
import re
import subprocess
import sys
import uuid

from pathlib import Path

from fastapi import APIRouter, Body, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse

from app.backup.events import EventBus
from app.backup.worker import BackupWorker


CHUNK_SIZE = 10 * 1024 * 1024  # 10MB
MAX_TOTAL_SIZE = 10 * 1024 * 1024 * 1024  # 10GB

_uploads: dict[str, dict] = {}
_uploads_lock = asyncio.Lock()


def _normalize_filename(name: str | None) -> str:
    base = Path(name or "uploaded_file").name
    base = re.sub(r'[<>:"|?*\x00-\x1f]', "_", base)
    return base or "uploaded_file"


def _validate_upload_id(upload_id: str) -> None:
    try:
        uuid.UUID(upload_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid upload_id")


def _append_bytes(path: Path, data: bytes) -> None:
    with open(path, "ab") as f:
        f.write(data)


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
    async def get_history(
        status: str | None = None,
        filter: str | None = None,
        channel_slug: str | None = None,
        category: str | None = None,
        page: int = 1,
        size: int = 50,
        sort: str = "backed_up_at",
        dir: str = "desc",
    ):
        """페이지네이션 + 정렬 지원. filter='download_incomplete'이면 수동 다운로드 필요 항목만.
        channel_slug/category는 채널별 카테고리 네임스페이스 구분을 위해 같이 받음."""
        from sqlalchemy import func as sql_func, nulls_last
        from app.db.engine import get_session
        from app.db.models import Article
        from sqlmodel import select as sql_select

        size = max(1, min(size, 200))
        page = max(1, page)
        offset = (page - 1) * size

        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            stmt = sql_select(Article)
            count_stmt = sql_select(sql_func.count(Article.id))

            if status:
                stmt = stmt.where(Article.backup_status == status)
                count_stmt = count_stmt.where(Article.backup_status == status)

            if filter == "download_incomplete":
                cond = (Article.backup_status == "completed") & (Article.download_complete == False) & (Article.analysis_status != "none")  # noqa: E712
                stmt = stmt.where(cond)
                count_stmt = count_stmt.where(cond)

            if channel_slug:
                stmt = stmt.where(Article.channel_slug == channel_slug)
                count_stmt = count_stmt.where(Article.channel_slug == channel_slug)

            if category is not None:
                # 빈 문자열이면 "카테고리 없음" (NULL)을 의미
                if category == "":
                    stmt = stmt.where(Article.category.is_(None))
                    count_stmt = count_stmt.where(Article.category.is_(None))
                else:
                    stmt = stmt.where(Article.category == category)
                    count_stmt = count_stmt.where(Article.category == category)

            # 정렬 컬럼 매핑
            sort_col_map = {
                "backed_up_at": Article.backed_up_at,
                "created_at": Article.created_at,
                "title": Article.title,
                "author": Article.author,
                "id": Article.id,
            }
            col = sort_col_map.get(sort, Article.backed_up_at)
            order_expr = col.desc() if dir.lower() != "asc" else col.asc()
            # NULL은 항상 뒤로
            stmt = stmt.order_by(nulls_last(order_expr), Article.id.desc())

            total = session.exec(count_stmt).one()
            articles = session.exec(stmt.offset(offset).limit(size)).all()
            items = [
                {
                    "id": a.id,
                    "channel_slug": a.channel_slug,
                    "title": a.title,
                    "author": a.author,
                    "category": a.category,
                    "backup_status": a.backup_status,
                    "backup_error": a.backup_error,
                    "backed_up_at": a.backed_up_at.isoformat() if a.backed_up_at else None,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "analysis_status": a.analysis_status,
                    "analysis_error": a.analysis_error,
                    "download_complete": a.download_complete,
                }
                for a in articles
            ]
            return {"items": items, "total": total, "page": page, "size": size}

    @router.get("/history/categories")
    async def history_categories():
        """백업된 article의 (channel_slug, category) 쌍과 개수. 이력 필터 UI용."""
        from sqlalchemy import func as sql_func
        from app.db.engine import get_session
        from app.db.models import Article
        from sqlmodel import select as sql_select

        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            rows = session.exec(
                sql_select(Article.channel_slug, Article.category, sql_func.count(Article.id))
                .group_by(Article.channel_slug, Article.category)
                .order_by(Article.channel_slug, Article.category)
            ).all()
            return [
                {
                    "channel_slug": r[0],
                    "category": r[1] or "",
                    "count": r[2],
                }
                for r in rows
            ]

    @router.post("/status")
    async def get_backup_statuses(ids: list[int] = Body(...)):
        from app.db.engine import get_session
        from app.db.repository import get_article
        from app.db.models import VersionGroup
        _engine = engine or worker._service._engine

        # 워커 큐에만 있고 DB에는 아직 없는 ID도 상태 반환 (enqueue 직후 새로고침 케이스)
        worker_status = worker.get_status() if worker else {"pending": [], "current": None}
        pending_ids = {r["article_id"] for r in worker_status.get("pending", [])}
        current = worker_status.get("current")
        current_id = current["article_id"] if current else None

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
                elif article_id == current_id:
                    result[str(article_id)] = {"status": "in_progress", "group_name": None, "group_id": None}
                elif article_id in pending_ids:
                    result[str(article_id)] = {"status": "pending", "group_name": None, "group_id": None}
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
                        "source_link_id": f.source_link_id,
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

    @router.post("/upload-free/init")
    async def upload_free_init(body: dict = Body(...)):
        article_id = body.get("article_id")
        filename = body.get("filename")
        total_size = body.get("total_size")
        total_chunks = body.get("total_chunks")
        note = body.get("note")

        if not isinstance(article_id, int):
            raise HTTPException(400, "article_id required (int)")
        if not isinstance(total_size, int) or total_size < 0:
            raise HTTPException(400, "total_size invalid")
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(413, f"file too large (max {MAX_TOTAL_SIZE} bytes)")
        expected_chunks = max(1, math.ceil(total_size / CHUNK_SIZE)) if total_size > 0 else 1
        if total_chunks != expected_chunks:
            raise HTTPException(400, f"total_chunks mismatch (expected {expected_chunks}, got {total_chunks})")

        safe_name = _normalize_filename(filename)
        upload_id = str(uuid.uuid4())

        data_dir = Path(worker._service._data_dir) if worker else Path("data")
        uploads_dir = data_dir / ".uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        temp_path = uploads_dir / f"{upload_id}.part"

        async with _uploads_lock:
            _uploads[upload_id] = {
                "article_id": article_id,
                "filename": safe_name,
                "total_size": total_size,
                "total_chunks": total_chunks,
                "received": 0,
                "note": note,
                "temp_path": str(temp_path),
            }

        return {"upload_id": upload_id}

    @router.post("/upload-free/chunk/{upload_id}")
    async def upload_free_chunk(upload_id: str, index: int, chunk: UploadFile = File(...)):
        _validate_upload_id(upload_id)

        async with _uploads_lock:
            meta = _uploads.get(upload_id)
            if not meta:
                raise HTTPException(404, "upload not found")
            if index != meta["received"]:
                raise HTTPException(400, f"out of order chunk (expected {meta['received']}, got {index})")
            if index >= meta["total_chunks"]:
                raise HTTPException(400, "chunk index out of range")

            data = await chunk.read()
            is_last = (index == meta["total_chunks"] - 1)
            if not is_last and len(data) != CHUNK_SIZE:
                raise HTTPException(400, f"non-final chunk must be exactly {CHUNK_SIZE} bytes")
            if is_last and len(data) > CHUNK_SIZE:
                raise HTTPException(400, "final chunk too large")

            temp_path = Path(meta["temp_path"])
            await asyncio.to_thread(_append_bytes, temp_path, data)
            meta["received"] = index + 1
            return {"received": meta["received"], "total": meta["total_chunks"]}

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
            if "source_link_id" in body:
                af.source_link_id = body["source_link_id"]
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
.arca-iframe-placeholder { display: inline-block; padding: 4px 10px; margin: 4px 0; border-radius: 6px; background: #f1f5f9; color: #64748b; font-size: 12px; border: 1px dashed #cbd5e1; user-select: none; }

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

    @router.post("/open-folder/{article_id}")
    async def open_backup_folder(article_id: int):
        """article의 백업 폴더를 OS 파일 탐색기로 연다.

        - data/articles/{id}/downloads/ 가 있으면 그 폴더를
        - 없으면 data/articles/{id}/ 를 연다
        - 둘 다 없으면 에러
        """
        data_dir = Path(worker._service._data_dir) if worker else Path("data")
        data_root = data_dir.resolve()

        article_dir = (data_dir / "articles" / str(article_id)).resolve()
        downloads_dir = article_dir / "downloads"
        target = (downloads_dir if downloads_dir.exists() else article_dir).resolve()

        # path traversal 방지: target이 data_root 하위인지 검증
        try:
            target.relative_to(data_root)
        except ValueError:
            return {"error": "invalid path"}

        if not target.exists():
            return {"error": "folder not found"}

        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(target)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except FileNotFoundError:
            return {"error": "file explorer not available"}
        except Exception as e:
            return {"error": f"failed to open: {e}"}

        return {"status": "opened", "path": str(target)}

    @router.post("/{channel_slug}/{article_id}")
    async def enqueue_backup(channel_slug: str, article_id: int, force: bool = False):
        if force:
            worker._service.reset_article_for_retry(article_id)
        position = await worker.enqueue(article_id, channel_slug, force=force)
        return {"status": "queued", "position": position}

    @router.delete("/{article_id}")
    async def cancel_backup(article_id: int):
        worker.cancel(article_id)
        return {"status": "cancelled"}

    @router.delete("/article/{article_id}")
    async def delete_article(article_id: int):
        """게시글을 DB와 파일에서 완전히 삭제. 큐에 있으면 먼저 취소."""
        worker.cancel(article_id)
        ok = worker._service.delete_article(article_id)
        if not ok:
            return {"error": "not found"}
        return {"status": "deleted"}

    @router.get("/candidates/{article_id}")
    async def related_candidates(article_id: int, min_similarity: float = 0.5, max_similarity: float = 0.8, limit: int = 10):
        """수동 승인용 관련 게시글 후보 (유사도 중간대). 자동 연결 안 함."""
        from app.llm.version import VersionDetector
        _engine = engine or worker._service._engine
        detector = VersionDetector(_engine)
        return await detector.find_candidates(article_id, min_similarity, max_similarity, limit)

    return router
