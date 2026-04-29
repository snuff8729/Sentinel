"""GET /api/image-meta?article_id=&url= — detect NAI metadata in an image.

Only namu CDN URLs are allowed (SSRF protection). Results cached in SQLite."""

from __future__ import annotations

import asyncio
from typing import Callable
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query

from app.image_meta.service import ImageMetaService

_MAX_URL_LEN = 2048
_ALLOWED_HOST_SUFFIX = ".namu.la"


def _validate_url(url: str) -> None:
    if len(url) > _MAX_URL_LEN:
        raise HTTPException(status_code=400, detail="url too long")
    if ".." in url:
        raise HTTPException(status_code=400, detail="url contains traversal")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="url scheme not allowed")
    host = (parsed.hostname or "").lower()
    if not host.endswith(_ALLOWED_HOST_SUFFIX):
        raise HTTPException(status_code=400, detail="url host not allowed")


def create_image_meta_router(
    engine,
    fetch_fn: Callable[[str], bytes | None] | None = None,
    parse_fn: Callable[[bytes], dict | None] | None = None,
) -> APIRouter:
    router = APIRouter()
    service = ImageMetaService(engine=engine, fetch_fn=fetch_fn, parse_fn=parse_fn)

    @router.get("")
    async def get_image_meta(
        article_id: int = Query(..., ge=0),
        url: str = Query(..., min_length=1),
        include: str | None = Query(None),
    ):
        _validate_url(url)
        include_full = include == "full"
        return await asyncio.to_thread(service.get_or_fetch, article_id, url, include_full)

    return router
