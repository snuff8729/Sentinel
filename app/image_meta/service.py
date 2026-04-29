"""Image metadata cache + fetch coordinator.

fetch_fn and parse_fn are injectable for tests. Defaults are httpx-based
fetch (defined in app.image_meta.fetcher, imported lazily) and the WebP/EXIF
parser from app.image_meta.parser."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Callable

from app.db.engine import get_session
from app.db.models import ImageMetaCache
from app.image_meta.parser import parse_has_nai

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
        parse_fn: Callable[[bytes], bool] | None = None,
    ):
        self._engine = engine
        self._fetch = fetch_fn or _default_fetch
        self._parse = parse_fn or parse_has_nai

    def get_or_fetch(self, article_id: int, url: str) -> dict:
        key = _make_key(article_id, url)
        with get_session(self._engine) as session:
            cached = session.get(ImageMetaCache, key)
            if cached is not None:
                return {"has_nai": cached.has_nai, "cached": True}

        body = self._fetch(url)
        if body is None:
            return {"has_nai": False, "cached": False}

        has_nai = self._parse(body)

        with get_session(self._engine) as session:
            session.add(
                ImageMetaCache(
                    key=key,
                    article_id=article_id,
                    has_nai=has_nai,
                    fetched_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

        return {"has_nai": has_nai, "cached": False}


def _default_fetch(url: str) -> bytes | None:
    # Lazy import: fetcher module ships in Task 4. Avoiding top-level import
    # so this module is testable without it (tests inject fetch_fn).
    from app.image_meta.fetcher import fetch_image_head_bytes
    return fetch_image_head_bytes(url)
