from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.backup.events import Event, EventBus
from app.backup.service import BackupService
from app.llm.service import LinkAnalysisService
from app.llm.version import VersionDetector

logger = logging.getLogger(__name__)


@dataclass
class BackupRequest:
    article_id: int
    channel_slug: str
    force: bool = False


class BackupWorker:
    def __init__(self, service: BackupService, event_bus: EventBus, link_analysis: LinkAnalysisService | None = None, version_detector: VersionDetector | None = None):
        self._service = service
        self._event_bus = event_bus
        self._link_analysis = link_analysis
        self._version_detector = version_detector
        self._queue: asyncio.Queue[BackupRequest] = asyncio.Queue()
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._cancelled: set[int] = set()
        self._current: BackupRequest | None = None
        self._pending: list[BackupRequest] = []

    async def enqueue(self, article_id: int, channel_slug: str, *, force: bool = False) -> int:
        req = BackupRequest(article_id=article_id, channel_slug=channel_slug, force=force)
        self._pending.append(req)
        await self._queue.put(req)
        self._event_bus.publish(Event(type="queue_updated", data=self._queue_snapshot()))
        return len(self._pending)

    def pause(self) -> None:
        self._pause_event.clear()
        logger.info("Worker paused")
        self._event_bus.publish(Event(type="worker_paused"))

    def resume(self) -> None:
        self._pause_event.set()
        logger.info("Worker resumed")
        self._event_bus.publish(Event(type="worker_resumed"))

    def cancel(self, article_id: int) -> None:
        self._cancelled.add(article_id)
        self._pending = [r for r in self._pending if r.article_id != article_id]
        logger.info("Cancelled article %d", article_id)
        self._event_bus.publish(Event(type="queue_updated", data=self._queue_snapshot()))

    def get_status(self) -> dict:
        current = None
        if self._current:
            current = {
                "article_id": self._current.article_id,
                "channel_slug": self._current.channel_slug,
            }
        return {
            "paused": not self._pause_event.is_set(),
            "current": current,
            "pending": [
                {"article_id": r.article_id, "channel_slug": r.channel_slug}
                for r in self._pending
            ],
        }

    async def run(self) -> None:
        # Startup recovery: reset in_progress articles to pending
        from app.db.engine import get_session
        from app.db.models import Article
        from sqlmodel import select

        engine = self._service._engine
        with get_session(engine) as session:
            stmt = select(Article).where(Article.backup_status == "in_progress")
            stuck = session.exec(stmt).all()
            for art in stuck:
                art.backup_status = "pending"
                session.add(art)
            if stuck:
                session.commit()
                logger.info("Recovered %d stuck articles to pending", len(stuck))

        logger.info("BackupWorker started")
        while True:
            req = await self._queue.get()
            self._pending = [r for r in self._pending if r.article_id != req.article_id]

            if req.article_id in self._cancelled:
                self._cancelled.discard(req.article_id)
                self._queue.task_done()
                continue

            await self._pause_event.wait()

            self._current = req
            logger.info("Processing article %d", req.article_id)

            try:
                await self._service.backup_article(
                    article_id=req.article_id,
                    channel_slug=req.channel_slug,
                    force=req.force,
                    pause_event=self._pause_event,
                    cancel_check=lambda aid=req.article_id: aid in self._cancelled,
                    event_bus=self._event_bus,
                )
                # 백업 성공 후 자동 처리
                if self._link_analysis:
                    try:
                        await self._link_analysis.analyze_article(req.article_id, req.channel_slug)
                    except Exception as e:
                        logger.error("Link analysis failed for %d: %s", req.article_id, e)
                if self._version_detector:
                    try:
                        if await self._version_detector.generate_embedding(req.article_id):
                            related = await self._version_detector.find_related(req.article_id)
                            if related:
                                for r in related:
                                    if r["relation"] in ("new_version", "same_series"):
                                        logger.info("[%d] 관련 게시글 발견: #%d (%s) — %s",
                                            req.article_id, r["article_id"], r["relation"], r["reason"])
                    except Exception as e:
                        logger.error("Version detection failed for %d: %s", req.article_id, e)
            except Exception as e:
                logger.error("Failed to backup article %d: %s", req.article_id, e)

            self._current = None
            self._queue.task_done()

    def _queue_snapshot(self) -> dict:
        return {
            "queue": [
                {"article_id": r.article_id, "channel_slug": r.channel_slug}
                for r in self._pending
            ],
        }
