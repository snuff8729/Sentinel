"""Saved image service: enqueue + dedup + get + list + delete.

`enqueue` is the only mutating entry point. It validates the URL whitelist,
extracts the content hash, performs (article_id, hex) dedup, and either
returns an existing row's status or inserts a new pending row."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, func
from sqlmodel import select

from app.db.engine import get_session
from app.db.models import Article, ImageTag, SavedImage, Tag
from app.image_meta.keys import extract_hex_from_url
from app.image_meta.validation import validate_url
from app.saved.tags import TagService


class SavedImageService:
    def __init__(self, engine, data_dir: str):
        self._engine = engine
        self._data_dir = data_dir
        self._tag_service = TagService(engine)

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
            d = row.model_dump(mode="json")
            article = session.get(Article, row.article_id)
            d["channel_slug"] = article.channel_slug if article else None
        if d.get("payload_json"):
            try:
                d["payload_json"] = json.loads(d["payload_json"])
            except (ValueError, TypeError):
                pass
        d["tags"] = self._tag_service.tags_for_image(save_id)
        return d

    def list_saved(
        self,
        offset: int = 0,
        limit: int = 60,
        untagged: bool = False,
        tag_prefix: str | None = None,
        no_exif: bool = False,
    ) -> dict:
        with get_session(self._engine) as session:
            base = select(SavedImage).where(SavedImage.status == "completed")
            if no_exif:
                base = base.where(SavedImage.payload_json.is_(None))
            if untagged:
                base = base.outerjoin(
                    ImageTag, ImageTag.image_id == SavedImage.id
                ).where(ImageTag.image_id.is_(None))
            elif tag_prefix:
                p = tag_prefix.strip().lower()
                escaped = p.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                base = (
                    base.join(ImageTag, ImageTag.image_id == SavedImage.id)
                    .join(Tag, Tag.id == ImageTag.tag_id)
                    .where(Tag.value.like(f"{escaped}%", escape="\\"))
                    .group_by(SavedImage.id)
                )
            count_stmt = select(func.count()).select_from(base.subquery())
            total = session.exec(count_stmt).one()
            rows = list(
                session.exec(
                    base.order_by(SavedImage.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                ).all()
            )

        items = []
        for r in rows:
            d = r.model_dump(mode="json")
            if d.get("payload_json"):
                try:
                    d["payload_json"] = json.loads(d["payload_json"])
                except (ValueError, TypeError):
                    pass
            items.append(d)
        ids = [r.id for r in rows]
        tags_map = self._tag_service.tags_for_images(ids)
        for item in items:
            item["tags"] = tags_map.get(item["id"], [])

        has_more = offset + len(items) < total
        return {"items": items, "total": total, "has_more": has_more}

    def queue_snapshot(self, recent_limit: int = 10) -> dict:
        with get_session(self._engine) as session:
            pending = list(session.exec(
                select(SavedImage).where(SavedImage.status == "pending")
                .order_by(SavedImage.created_at)
            ).all())
            in_progress = list(session.exec(
                select(SavedImage).where(SavedImage.status == "in_progress")
                .order_by(SavedImage.created_at)
            ).all())
            failed = list(session.exec(
                select(SavedImage).where(SavedImage.status == "failed")
                .order_by(SavedImage.created_at.desc())
            ).all())
            completed = list(session.exec(
                select(SavedImage).where(SavedImage.status == "completed")
                .order_by(SavedImage.completed_at.desc())
                .limit(recent_limit)
            ).all())

            article_ids = {r.article_id for r in pending + in_progress + failed + completed}
            slug_by_id: dict[int, str] = {}
            if article_ids:
                rows = session.exec(
                    select(Article.id, Article.channel_slug).where(Article.id.in_(article_ids))
                ).all()
                slug_by_id = {a_id: slug for a_id, slug in rows}

        def serialize(rows: list[SavedImage]) -> list[dict]:
            return [
                {
                    "id": r.id,
                    "article_id": r.article_id,
                    "channel_slug": slug_by_id.get(r.article_id),
                    "hex": r.hex,
                    "status": r.status,
                    "retry_count": r.retry_count,
                    "error": r.error,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }
                for r in rows
            ]

        return {
            "pending": serialize(pending),
            "in_progress": serialize(in_progress),
            "failed": serialize(failed),
            "recent_completed": serialize(completed),
        }

    def delete_saved(self, save_id: int) -> bool:
        with get_session(self._engine) as session:
            row = session.get(SavedImage, save_id)
            if row is None:
                return False
            file_path = row.file_path
            session.exec(delete(ImageTag).where(ImageTag.image_id == save_id))
            session.delete(row)
            session.commit()

        if file_path:
            png = Path(self._data_dir) / file_path
            json_sidecar = png.with_suffix(".json")
            try:
                png.unlink(missing_ok=True)
            except Exception:
                pass
            try:
                json_sidecar.unlink(missing_ok=True)
            except Exception:
                pass
            try:
                png.parent.rmdir()
            except OSError:
                pass
        return True
