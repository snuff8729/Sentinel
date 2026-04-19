from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.backup.downloader import ExternalDownloader
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
    def __init__(self, service: BackupService, event_bus: EventBus, link_analysis: LinkAnalysisService | None = None, version_detector: VersionDetector | None = None, downloader: ExternalDownloader | None = None):
        self._service = service
        self._event_bus = event_bus
        self._link_analysis = link_analysis
        self._version_detector = version_detector
        self._downloader = downloader
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
        # Startup recovery:
        # 1) in_progress → pending (서버 종료 시점에 처리 중이던 글)
        # 2) pending 상태 글을 모두 큐에 다시 넣음 (DB에는 대기로 보이는데 실제 큐에 없던 버그 방지)
        from app.db.engine import get_session
        from app.db.models import Article
        from sqlmodel import select

        engine = self._service._engine
        with get_session(engine) as session:
            for art in session.exec(select(Article).where(Article.backup_status == "in_progress")).all():
                art.backup_status = "pending"
                session.add(art)
            session.commit()

            pending_articles = list(
                session.exec(
                    select(Article).where(Article.backup_status == "pending").order_by(Article.id.asc())
                ).all()
            )
            requeue = [(a.id, a.channel_slug) for a in pending_articles]

        if requeue:
            for aid, slug in requeue:
                await self.enqueue(aid, slug, force=False)
            logger.info("Startup recovery: %d 게시글을 큐에 재투입", len(requeue))

        logger.info("BackupWorker started")
        while True:
            req = await self._queue.get()
            self._pending = [r for r in self._pending if r.article_id != req.article_id]
            self._event_bus.publish(Event(type="queue_updated", data=self._queue_snapshot()))

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
                # 외부 다운로드 링크 자동 다운로드
                if self._downloader:
                    try:
                        await self._download_external_links(req.article_id)
                    except Exception as e:
                        logger.error("External download failed for %d: %s", req.article_id, e)
                if self._version_detector:
                    try:
                        embedding_ok = await self._version_detector.generate_embedding(req.article_id)
                        # 재시도(force=True)일 땐 기존 버전 그룹을 그대로 유지해야 하므로 자동 연결 스킵
                        if embedding_ok and not req.force:
                            related = await self._version_detector.find_related(req.article_id)
                            if related:
                                for r in related:
                                    if r["relation"] in ("new_version", "same_series"):
                                        logger.info("[%d] 관련 게시글 발견: #%d (%s) — %s",
                                            req.article_id, r["article_id"], r["relation"], r["reason"])
                        elif embedding_ok and req.force:
                            logger.info("[%d] 재시도 — 자동 버전 그룹 연결 스킵", req.article_id)
                    except Exception as e:
                        logger.error("Version detection failed for %d: %s", req.article_id, e)
            except Exception as e:
                logger.error("Failed to backup article %d: %s", req.article_id, e)

            self._current = None
            self._queue.task_done()

    async def _download_external_links(self, article_id: int) -> None:
        """다운로드 타입 링크를 자동으로 다운로드."""
        from app.db.engine import get_session
        from app.db.repository import get_links_for_article
        from app.db.models import ArticleFile

        with get_session(self._service._engine) as session:
            links = get_links_for_article(session, article_id)
            download_links = [l for l in links if l.link_type == "download"]

        if not download_links:
            return

        logger.info("[%d] 외부 다운로드 %d개 시작", article_id, len(download_links))

        for link in download_links:
            result = await self._downloader.download(link.url, article_id)

            if result["success"]:
                logger.info("[%d] 외부 다운로드 완료: %s (%.1fKB)",
                    article_id, result["filename"], result["size"] / 1024)
                # 첨부 파일로 기록
                with get_session(self._service._engine) as session:
                    af = ArticleFile(
                        article_id=article_id,
                        filename=result["filename"],
                        local_path=result["local_path"],
                        size=result["size"],
                        note=f"자동 다운로드: {link.url}",
                        source_link_id=link.id,
                    )
                    session.add(af)
                    session.commit()
            elif result["manual_required"]:
                logger.info("[%d] 수동 다운로드 필요: %s", article_id, result["error"])
            else:
                logger.warning("[%d] 외부 다운로드 실패: %s", article_id, result["error"])

        # 전체 자동 완료 체크
        self._check_download_complete(article_id)

    def _check_download_complete(self, article_id: int) -> None:
        """모든 다운로드 링크에 대응하는 파일이 있으면 download_complete = True."""
        from app.db.engine import get_session
        from app.db.repository import get_links_for_article
        from app.db.models import Article, ArticleFile
        from sqlmodel import select

        with get_session(self._service._engine) as session:
            links = get_links_for_article(session, article_id)
            download_links = [l for l in links if l.link_type == "download"]
            if not download_links:
                return

            files = session.exec(select(ArticleFile).where(ArticleFile.article_id == article_id)).all()
            downloaded_link_ids = {f.source_link_id for f in files if f.source_link_id}

            all_handled = all(l.id in downloaded_link_ids for l in download_links)

            if all_handled:
                article = session.get(Article, article_id)
                if article:
                    article.download_complete = True
                    session.add(article)
                    session.commit()
                    logger.info("[%d] 모든 외부 다운로드 완료", article_id)

    def _queue_snapshot(self) -> dict:
        return {
            "queue": [
                {"article_id": r.article_id, "channel_slug": r.channel_slug}
                for r in self._pending
            ],
        }
