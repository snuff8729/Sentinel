"""Saved image service: enqueue + dedup + get.

`enqueue` is the only mutating entry point. It validates the URL whitelist,
extracts the content hash, performs (article_id, hex) dedup, and either
returns an existing row's status or inserts a new pending row."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import select

from app.db.engine import get_session
from app.db.models import SavedImage
from app.image_meta.keys import extract_hex_from_url
from app.image_meta.validation import validate_url


class SavedImageService:
    def __init__(self, engine, data_dir: str):
        self._engine = engine
        self._data_dir = data_dir

    def enqueue(self, article_id: int, url: str) -> dict:
        try:
            validate_url(url)
        except HTTPException as e:
            return {"status": "error", "error": str(e.detail)}

        hex_id = extract_hex_from_url(url)
        with get_session(self._engine) as session:
            existing = session.exec(
                select(SavedImage).where(
                    SavedImage.article_id == article_id,
                    SavedImage.hex == hex_id,
                )
            ).first()
            if existing is not None:
                if existing.status == "completed":
                    return {"status": "already_saved", "id": existing.id}
                if existing.status in ("pending", "in_progress"):
                    return {"status": "queued", "id": existing.id}
                # failed → reset for retry
                existing.status = "pending"
                existing.retry_count = 0
                existing.error = None
                session.add(existing)
                session.commit()
                return {"status": "queued", "id": existing.id}

            row = SavedImage(
                article_id=article_id,
                hex=hex_id,
                src_url=url,
                status="pending",
                created_at=datetime.now(timezone.utc),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return {"status": "queued", "id": row.id}

    def get(self, save_id: int) -> dict | None:
        with get_session(self._engine) as session:
            row = session.get(SavedImage, save_id)
            if row is None:
                return None
            return row.model_dump()
