"""Image metadata cache + fetch coordinator.

fetch_fn returns image bytes (or None on failure). parse_fn returns the full
NAI metadata dict (or None if not NAI). Both are injectable for tests."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Callable

from app.db.engine import get_session
from app.db.models import ImageMetaCache
from app.image_meta.parser import parse_nai_metadata

_HEX64_RE = re.compile(r"[a-fA-F0-9]{64}")


def _make_key(article_id: int, url: str) -> str:
    m = _HEX64_RE.search(url)
    if m:
        return f"{article_id}_{m.group(0).lower()}"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return f"{article_id}_{digest}"


class ImageMetaService:
    def __init__(
        self,
        engine,
        fetch_fn: Callable[[str], bytes | None] | None = None,
        parse_fn: Callable[[bytes], dict | None] | None = None,
    ):
        self._engine = engine
        self._fetch = fetch_fn or _default_fetch
        self._parse = parse_fn or parse_nai_metadata

    def get_or_fetch(self, article_id: int, url: str, include_full: bool = False) -> dict:
        key = _make_key(article_id, url)
        with get_session(self._engine) as session:
            cached = session.get(ImageMetaCache, key)
            if cached is not None and (not include_full or cached.payload_json is not None):
                result = {"has_nai": cached.has_nai, "cached": True}
                if include_full and cached.payload_json:
                    result["metadata"] = json.loads(cached.payload_json)
                return result

        body = self._fetch(url)
        if body is None:
            return {"has_nai": False, "cached": False}

        metadata = self._parse(body)
        has_nai = metadata is not None
        payload_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

        with get_session(self._engine) as session:
            session.merge(ImageMetaCache(
                key=key,
                article_id=article_id,
                has_nai=has_nai,
                payload_json=payload_json,
                fetched_at=datetime.now(timezone.utc),
            ))
            session.commit()

        result = {"has_nai": has_nai, "cached": False}
        if include_full and metadata is not None:
            result["metadata"] = metadata
        return result


def _default_fetch(url: str) -> bytes | None:
    from app.image_meta.fetcher import fetch_image_head_bytes
    return fetch_image_head_bytes(url)
