from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from sqlmodel import Session

from app.backup.media import MediaItem, extract_media_from_html, replace_urls_in_html
from app.backup.queue import DownloadQueue
from app.db.engine import get_session
from app.db.models import Article
from app.db.repository import (
    create_article,
    create_download,
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
    ) -> None:
        with get_session(self._engine) as session:
            if not force and is_article_completed(session, article_id):
                return

            # 1. Fetch detail page
            logger.info("[%d] 상세 페이지 가져오는 중...", article_id)
            resp = await asyncio.to_thread(
                self._client.get, f"/b/{channel_slug}/{article_id}"
            )
            html = resp.text

            # 2. Parse meta + create/update Article record
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

        # 3. Extract media — 아카콘과 일반 미디어 분리
        media_items = extract_media_from_html(html, article_id)
        emoticons = [m for m in media_items if m.file_type == "emoticon"]
        media = [m for m in media_items if m.file_type != "emoticon"]
        logger.info(
            "[%d] 미디어 %d개 발견 (일반 %d + 아카콘 %d)",
            article_id, len(media_items), len(media), len(emoticons),
        )

        # 4. Create Download records
        with get_session(self._engine) as session:
            if force:
                for dl in get_downloads_for_article(session, article_id):
                    update_download_status(session, dl.id, "pending")

            for item in media_items:
                existing = get_downloads_for_article(session, article_id)
                urls = {d.url for d in existing}
                if item.url not in urls:
                    create_download(
                        session,
                        article_id=article_id,
                        url=item.url,
                        local_path=item.local_path,
                        file_type=item.file_type,
                    )

        # 5a. 아카콘 — 병렬 다운로드, 이미 존재하면 스킵 (큐 안 탐)
        emoticon_results = await self._download_emoticons(article_id, emoticons)

        # 5b. 일반 미디어 — 순차 다운로드
        media_results = await self._download_media(article_id, media)

        completed_count = emoticon_results["completed"] + media_results["completed"]
        failed_count = emoticon_results["failed"] + media_results["failed"]
        skipped_count = emoticon_results["skipped"]

        logger.info(
            "[%d] 다운로드 완료: %d 성공, %d 스킵(아카콘), %d 실패",
            article_id, completed_count, skipped_count, failed_count,
        )

        # 6. Replace URLs + save backup HTML
        url_to_relative = {m.url: m.relative_path for m in media_items}
        backup_html = replace_urls_in_html(html, url_to_relative)
        backup_path = self._data_dir / "articles" / str(article_id) / "backup.html"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(backup_html, encoding="utf-8")

        # 7. Final status
        with get_session(self._engine) as session:
            if failed_count > 0:
                update_article_status(
                    session, article_id, "failed",
                    error=f"{failed_count} file(s) failed to download",
                )
            else:
                update_article_status(session, article_id, "completed")

    async def _download_emoticons(
        self, article_id: int, emoticons: list[MediaItem]
    ) -> dict[str, int]:
        """아카콘을 병렬로 다운로드. 이미 존재하면 스킵."""
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
            except Exception as e:
                results["failed"] += 1
                logger.warning("[%d] 아카콘 실패: %s — %s", article_id, dest.name, e)
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "failed", error=str(e))
                            break

        await asyncio.gather(*[_download_one(item) for item in emoticons])
        return results

    async def _download_media(
        self, article_id: int, media: list[MediaItem]
    ) -> dict[str, int]:
        """일반 미디어를 순차 다운로드."""
        results = {"completed": 0, "failed": 0}
        total = len(media)
        if not total:
            return results

        for i, item in enumerate(media, 1):
            dest = self._data_dir / item.local_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            try:
                file_resp = await asyncio.to_thread(self._client.get, item.url)
                dest.write_bytes(file_resp.content)
                results["completed"] += 1
                size_kb = len(file_resp.content) / 1024
                logger.info(
                    "[%d] [%d/%d] ✓ %s %.1fKB (%s)",
                    article_id, i, total, dest.name, size_kb, item.file_type,
                )
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "completed")
                            break
            except Exception as e:
                results["failed"] += 1
                logger.warning(
                    "[%d] [%d/%d] ✗ %s 실패: %s",
                    article_id, i, total, dest.name, e,
                )
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "failed", error=str(e))
                            break

        return results
