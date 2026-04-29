"""Tag CRUD + assignment service for saved images.

Tags are flat (no type) and stored lowercase/trimmed; user convention
(e.g., 'character:miku', 'artist:foo') gives them implicit grouping
via prefix matching."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.db.engine import get_session
from app.db.models import ImageTag, Tag

_MAX_TAG_LEN = 200


class TagService:
    def __init__(self, engine):
        self._engine = engine

    def get_or_create(self, value: str) -> Tag:
        v = (value or "").strip().lower()
        if not v:
            raise ValueError("tag value cannot be empty")
        if len(v) > _MAX_TAG_LEN:
            raise ValueError(f"tag value exceeds {_MAX_TAG_LEN} chars")
        with get_session(self._engine) as session:
            existing = session.exec(select(Tag).where(Tag.value == v)).first()
            if existing is not None:
                return existing
            tag = Tag(value=v, created_at=datetime.now(timezone.utc))
            session.add(tag)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                refetched = session.exec(select(Tag).where(Tag.value == v)).first()
                if refetched is None:
                    raise
                return refetched
            session.refresh(tag)
            return tag

    def find_by_prefix(self, prefix: str, limit: int = 20) -> list[Tag]:
        p = (prefix or "").strip().lower()
        with get_session(self._engine) as session:
            if not p:
                stmt = select(Tag).order_by(Tag.value).limit(limit)
            else:
                escaped = p.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                stmt = (
                    select(Tag)
                    .where(Tag.value.like(f"{escaped}%", escape="\\"))
                    .order_by(Tag.value)
                    .limit(limit)
                )
            return list(session.exec(stmt).all())

    def assign(self, image_id: int, tag_id: int) -> None:
        with get_session(self._engine) as session:
            existing = session.exec(
                select(ImageTag).where(
                    ImageTag.image_id == image_id, ImageTag.tag_id == tag_id
                )
            ).first()
            if existing is not None:
                return
            session.add(ImageTag(
                image_id=image_id,
                tag_id=tag_id,
                assigned_at=datetime.now(timezone.utc),
            ))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()

    def unassign(self, image_id: int, tag_id: int) -> None:
        with get_session(self._engine) as session:
            row = session.exec(
                select(ImageTag).where(
                    ImageTag.image_id == image_id, ImageTag.tag_id == tag_id
                )
            ).first()
            if row is not None:
                session.delete(row)
                session.commit()

    def tags_for_image(self, image_id: int) -> list[dict]:
        with get_session(self._engine) as session:
            rows = session.exec(
                select(Tag)
                .join(ImageTag, ImageTag.tag_id == Tag.id)
                .where(ImageTag.image_id == image_id)
                .order_by(Tag.value)
            ).all()
            return [{"id": r.id, "value": r.value} for r in rows]

    def tags_for_images(self, image_ids: list[int]) -> dict[int, list[dict]]:
        if not image_ids:
            return {}
        with get_session(self._engine) as session:
            rows = session.exec(
                select(ImageTag.image_id, Tag.id, Tag.value)
                .join(Tag, Tag.id == ImageTag.tag_id)
                .where(ImageTag.image_id.in_(image_ids))
                .order_by(ImageTag.image_id, Tag.value)
            ).all()
        out: dict[int, list[dict]] = {iid: [] for iid in image_ids}
        for image_id, tag_id, value in rows:
            out[image_id].append({"id": tag_id, "value": value})
        return out
