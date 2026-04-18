from __future__ import annotations

import asyncio
from pathlib import Path

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
            resp = await asyncio.to_thread(
                self._client.get, f"/b/{channel_slug}/{article_id}"
            )
            html = resp.text

            # 2. Parse meta + create/update Article record
            detail = parse_article_detail(html, article_id)
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

        # 3. Extract media
        media_items = extract_media_from_html(html, article_id)

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

        # 5. Download files
        failed_count = 0
        url_to_relative: dict[str, str] = {}

        for item in media_items:
            url_to_relative[item.url] = item.relative_path
            dest = self._data_dir / item.local_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Skip existing emoticons
            if item.file_type == "emoticon" and dest.exists():
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "completed")
                            break
                continue

            try:
                file_resp = await asyncio.to_thread(self._client.get, item.url)
                dest.write_bytes(file_resp.content)
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "completed")
                            break
            except Exception as e:
                failed_count += 1
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "failed", error=str(e))
                            break

        # 6. Replace URLs + save backup HTML
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
