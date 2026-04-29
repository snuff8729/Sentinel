"""Library service for bulk-importing local images into the saved-image gallery.

Library rows have source='library', article_id=0 (sentinel — article_id has
no FK constraint at the SQL level), status='completed' on insert (no download
pipeline involvement). Dedup is by sha256 of file content within the
(article_id=0, hex) bucket — the existing unique index on (article_id, hex)
provides this for free."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import select

from app.db.engine import get_session
from app.db.models import SavedImage
from app.image_meta.parser import parse_nai_metadata
from app.saved.library_storage import write_library_image

_SUPPORTED_EXTS = {"png", "jpg", "jpeg", "webp"}


class LibraryService:
    def __init__(self, engine, data_dir: str):
        self._engine = engine
        self._data_dir = data_dir

    def import_image(self, file_path: str | Path) -> dict:
        path = Path(file_path)
        if not path.is_file():
            return {"status": "skipped", "reason": "file not found"}
        ext = path.suffix.lstrip(".").lower()
        if ext not in _SUPPORTED_EXTS:
            return {"status": "skipped", "reason": f"unsupported extension: {ext}"}
        if ext == "jpeg":
            ext = "jpg"

        buf = path.read_bytes()
        hex_id = hashlib.sha256(buf).hexdigest()

        with get_session(self._engine) as session:
            existing = session.exec(
                select(SavedImage).where(
                    SavedImage.article_id == 0,
                    SavedImage.hex == hex_id,
                    SavedImage.source == "library",
                )
            ).first()
            if existing is not None:
                return {"status": "already_imported", "id": existing.id}

        metadata = parse_nai_metadata(buf)
        rel_path = write_library_image(self._data_dir, hex_id, ext, buf, metadata)

        now = datetime.now(timezone.utc)
        with get_session(self._engine) as session:
            row = SavedImage(
                article_id=0,
                hex=hex_id,
                src_url="",
                file_path=rel_path,
                payload_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
                status="completed",
                created_at=now,
                completed_at=now,
                source="library",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return {"status": "imported", "id": row.id}
