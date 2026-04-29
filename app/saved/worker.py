"""Background worker for saved-image queue.

Polls SavedImage rows where status='pending', processes one at a time
(concurrency 1, mindful of arca CDN rate limits). On exception, retries
up to 3 times with exponential backoff (2s, 4s, 8s). Resets in_progress
zombies to pending on startup. Publishes `saved_queue_updated` events
on every state transition for SSE consumers."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlmodel import select

from app.backup.events import Event, EventBus
from app.db.engine import get_session
from app.db.models import SavedImage
from app.image_meta.fetcher import fetch_full_image
from app.image_meta.parser import parse_nai_metadata
from app.saved.service import SavedImageService
from app.saved.storage import write_saved_image

logger = logging.getLogger(__name__)


class SavedImageWorker:
    def __init__(
        self,
        engine,
        data_dir: str,
        signal: asyncio.Event,
        event_bus: EventBus | None = None,
    ):
        self._engine = engine
        self._data_dir = data_dir
        self._signal = signal
        self._stop = False
        self._event_bus = event_bus
        self._service = SavedImageService(engine=engine, data_dir=data_dir)

    async def run(self):
        await asyncio.to_thread(self._reset_zombies)
        await self._publish_snapshot()
        while not self._stop:
            row = await asyncio.to_thread(self._claim_next_pending)
            if row is None:
                try:
                    await asyncio.wait_for(self._signal.wait(), timeout=30)
                    self._signal.clear()
                except asyncio.TimeoutError:
                    pass
                continue
            await self._publish_snapshot()
            await self._process(row)
            await self._publish_snapshot()

    async def _publish_snapshot(self):
        if self._event_bus is None:
            return
        snap = await asyncio.to_thread(self._service.queue_snapshot)
        self._event_bus.publish(Event(type="saved_queue_updated", data=snap))

    def _reset_zombies(self):
        with get_session(self._engine) as session:
            rows = session.exec(
                select(SavedImage).where(SavedImage.status == "in_progress")
            ).all()
            for r in rows:
                r.status = "pending"
                session.add(r)
            session.commit()

    def _claim_next_pending(self):
        with get_session(self._engine) as session:
            row = session.exec(
                select(SavedImage)
                .where(SavedImage.status == "pending")
                .order_by(SavedImage.created_at)
                .limit(1)
            ).first()
            if row is None:
                return None
            row.status = "in_progress"
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    async def _process(self, row: SavedImage):
        try:
            buf = await asyncio.to_thread(fetch_full_image, row.src_url)
            if buf is None:
                raise RuntimeError("fetch returned None")
            metadata = await asyncio.to_thread(parse_nai_metadata, buf)
            file_path = await asyncio.to_thread(
                write_saved_image, self._data_dir, row.article_id, row.hex, buf, metadata,
            )
            await asyncio.to_thread(self._mark_completed, row.id, file_path, metadata)
        except Exception as e:
            logger.warning("save process failed for id=%s: %s", row.id, e)
            await self._handle_failure(row, str(e))

    def _mark_completed(self, row_id: int, file_path: str, metadata: dict | None):
        with get_session(self._engine) as session:
            row = session.get(SavedImage, row_id)
            row.status = "completed"
            row.file_path = file_path
            row.payload_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
            row.completed_at = datetime.now(timezone.utc)
            session.add(row)
            session.commit()

    async def _handle_failure(self, row: SavedImage, error_msg: str):
        new_count = row.retry_count + 1
        if new_count < 3:
            await asyncio.sleep(2 ** new_count)
            await asyncio.to_thread(self._reset_for_retry, row.id, new_count, error_msg)
        else:
            await asyncio.to_thread(self._mark_failed, row.id, new_count, error_msg)

    def _reset_for_retry(self, row_id: int, count: int, error: str):
        with get_session(self._engine) as session:
            row = session.get(SavedImage, row_id)
            row.status = "pending"
            row.retry_count = count
            row.error = error
            session.add(row)
            session.commit()

    def _mark_failed(self, row_id: int, count: int, error: str):
        with get_session(self._engine) as session:
            row = session.get(SavedImage, row_id)
            row.status = "failed"
            row.retry_count = count
            row.error = error
            session.add(row)
            session.commit()
