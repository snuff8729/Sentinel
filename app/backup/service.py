from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

from app.backup.events import Event, EventBus
from app.backup.media import MediaItem, extract_media_from_html, replace_urls_in_html
from app.backup.queue import DownloadQueue
from app.db.engine import get_session
from app.db.repository import (
    create_article,
    create_download,
    delete_downloads_for_article,
    get_article,
    get_downloads_for_article,
    is_article_completed,
    update_article_status,
    update_download_status,
)
from app.scraper.arca.parser import parse_article_detail


class BackupService:
    def __init__(self, engine, client, data_dir: str = "data"):
        self._engine = engine
        self._client = client
        self._data_dir = Path(data_dir)
        self._queue = DownloadQueue()

    async def backup_article(
        self,
        article_id: int,
        channel_slug: str,
        *,
        force: bool = False,
        pause_event: asyncio.Event | None = None,
        cancel_check: Callable[[], bool] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        def _emit(event_type: str, data: dict | None = None):
            if event_bus:
                event_bus.publish(Event(type=event_type, data=data or {}))

        with get_session(self._engine) as session:
            if not force and is_article_completed(session, article_id):
                return

            logger.info("[%d] 상세 페이지 가져오는 중...", article_id)
            resp = await asyncio.to_thread(
                self._client.get, f"/b/{channel_slug}/{article_id}"
            )
            html = resp.text

            detail = parse_article_detail(html, article_id)
            logger.info("[%d] '%s' by %s", article_id, detail.title, detail.author)
            article = get_article(session, article_id)
            if article is None:
                article = create_article(
                    session,
                    id=article_id,
                    channel_slug=channel_slug,
                    title=detail.title,
                    author=detail.author,
                    category=detail.category,
                    created_at=detail.created_at,
                    url=f"https://arca.live/b/{channel_slug}/{article_id}",
                )
            update_article_status(session, article_id, "in_progress")

        media_items = extract_media_from_html(html, article_id)
        emoticons = [m for m in media_items if m.file_type == "emoticon"]
        media = [m for m in media_items if m.file_type != "emoticon"]
        total_files = len(media_items)
        logger.info(
            "[%d] 미디어 %d개 발견 (일반 %d + 아카콘 %d)",
            article_id, total_files, len(media), len(emoticons),
        )

        _emit("article_started", {
            "article_id": article_id,
            "title": detail.title,
            "total_files": total_files,
        })

        if cancel_check and cancel_check():
            with get_session(self._engine) as session:
                update_article_status(session, article_id, "cancelled")
            return

        with get_session(self._engine) as session:
            if force:
                delete_downloads_for_article(session, article_id)

            existing_urls = {d.url for d in get_downloads_for_article(session, article_id)}
            for item in media_items:
                if item.url not in existing_urls:
                    create_download(
                        session,
                        article_id=article_id,
                        url=item.url,
                        local_path=item.local_path,
                        file_type=item.file_type,
                        warning=item.warning,
                    )
                    existing_urls.add(item.url)

        emoticon_results = await self._download_emoticons(article_id, emoticons, _emit)

        media_results = await self._download_media(
            article_id, media, _emit,
            pause_event=pause_event,
            cancel_check=cancel_check,
        )

        completed_count = emoticon_results["completed"] + media_results["completed"]
        failed_count = emoticon_results["failed"] + media_results["failed"]
        skipped_count = emoticon_results["skipped"]
        cancelled = media_results.get("cancelled", False)

        logger.info(
            "[%d] 다운로드 완료: %d 성공, %d 스킵(아카콘), %d 실패%s",
            article_id, completed_count, skipped_count, failed_count,
            " (취소됨)" if cancelled else "",
        )

        url_to_relative = {m.url: m.relative_path for m in media_items}
        backup_html = replace_urls_in_html(html, url_to_relative)
        backup_path = self._data_dir / "articles" / str(article_id) / "backup.html"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(backup_html, encoding="utf-8")

        with get_session(self._engine) as session:
            if cancelled:
                update_article_status(session, article_id, "cancelled")
            elif failed_count > 0:
                update_article_status(
                    session, article_id, "failed",
                    error=f"{failed_count} file(s) failed to download",
                )
            else:
                update_article_status(session, article_id, "completed")

        _emit("article_completed", {
            "article_id": article_id,
            "success_count": completed_count,
            "fail_count": failed_count,
        })

    async def _download_emoticons(
        self, article_id: int, emoticons: list[MediaItem], emit,
    ) -> dict[str, int]:
        results = {"completed": 0, "failed": 0, "skipped": 0}
        if not emoticons:
            return results

        async def _download_one(item: MediaItem):
            dest = self._data_dir / item.local_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            if dest.exists():
                results["skipped"] += 1
                logger.info("[%d] 아카콘 스킵: %s (이미 존재)", article_id, dest.name)
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "completed")
                            break
                return

            try:
                file_resp = await asyncio.to_thread(self._client.get, item.url)
                dest.write_bytes(file_resp.content)
                results["completed"] += 1
                logger.info(
                    "[%d] 아카콘 다운: %s %.1fKB",
                    article_id, dest.name, len(file_resp.content) / 1024,
                )
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "completed")
                            break
                emit("file_completed", {
                    "article_id": article_id,
                    "filename": dest.name,
                    "size_kb": round(len(file_resp.content) / 1024, 1),
                    "file_type": "emoticon",
                })
            except Exception as e:
                results["failed"] += 1
                logger.warning("[%d] 아카콘 실패: %s — %s", article_id, dest.name, e)
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "failed", error=str(e))
                            break
                emit("file_failed", {
                    "article_id": article_id,
                    "filename": dest.name,
                    "error": str(e),
                })

        await asyncio.gather(*[_download_one(item) for item in emoticons])
        return results

    async def _download_media(
        self,
        article_id: int,
        media: list[MediaItem],
        emit,
        *,
        pause_event: asyncio.Event | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict:
        results = {"completed": 0, "failed": 0, "cancelled": False}
        total = len(media)
        if not total:
            return results

        completed_so_far = 0

        async def _do_download(url: str, dest_str: str):
            nonlocal completed_so_far
            dest = Path(dest_str)
            item = next(m for m in media if m.url == url)
            if item.warning:
                logger.warning("[%d] ⚠ %s: %s", article_id, dest.name, item.warning)
                completed_so_far += 1
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == url:
                            update_download_status(session, dl.id, "completed")
                            break
                return
            try:
                file_resp = await asyncio.to_thread(self._client.get, url)
                dest.write_bytes(file_resp.content)
                results["completed"] += 1
                completed_so_far += 1
                size_kb = len(file_resp.content) / 1024
                logger.info(
                    "[%d] [%d/%d] ✓ %s %.1fKB (%s)",
                    article_id, completed_so_far, total, dest.name, size_kb, item.file_type,
                )
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == url:
                            update_download_status(session, dl.id, "completed")
                            break
                emit("file_completed", {
                    "article_id": article_id,
                    "filename": dest.name,
                    "size_kb": round(size_kb, 1),
                    "current": completed_so_far,
                    "total": total,
                    "file_type": item.file_type,
                })
            except Exception as e:
                results["failed"] += 1
                completed_so_far += 1
                logger.warning(
                    "[%d] [%d/%d] ✗ %s 실패: %s",
                    article_id, completed_so_far, total, dest.name, e,
                )
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == url:
                            update_download_status(session, dl.id, "failed", error=str(e))
                            break
                emit("file_failed", {
                    "article_id": article_id,
                    "filename": dest.name,
                    "error": str(e),
                })

        for item in media:
            if cancel_check and cancel_check():
                results["cancelled"] = True
                break

            dest = self._data_dir / item.local_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            await self._queue.submit(
                url=item.url,
                dest=str(dest),
                download_fn=_do_download,
                pause_event=pause_event,
                cancel_check=cancel_check,
            )

        await self._queue.wait_all()
        return results
