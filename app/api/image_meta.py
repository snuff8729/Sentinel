"""GET /api/image-meta?article_id=&url= — detect NAI metadata in an image.

Only namu CDN URLs are allowed (SSRF protection). Results cached in SQLite."""

from __future__ import annotations

import asyncio
from typing import Callable

from fastapi import APIRouter, Query

from app.image_meta.service import ImageMetaService
from app.image_meta.validation import validate_url


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
        validate_url(url)
        include_full = include == "full"
        return await asyncio.to_thread(service.get_or_fetch, article_id, url, include_full)

    return router
