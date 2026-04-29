"""POST /api/saved-images { article_id, url } enqueues an image save.
GET /api/saved-images/{id} returns the row state (debug + Spec 2 use).

Service returns error responses with status='error' in the body (200);
HTTP 400 is reserved for malformed payloads (missing article_id/url)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from app.saved.service import SavedImageService
from app.saved.tags import TagService


def create_saved_router(engine, data_dir: str, worker_signal: asyncio.Event) -> APIRouter:
    router = APIRouter()
    service = SavedImageService(engine=engine, data_dir=data_dir)
    tag_service = TagService(engine)

    @router.post("")
    async def enqueue_save(payload: dict):
        article_id = payload.get("article_id")
        url = payload.get("url")
        if not isinstance(article_id, int) or article_id <= 0 or not isinstance(url, str) or not url:
            raise HTTPException(status_code=400, detail="missing or invalid article_id/url")
        result = await asyncio.to_thread(service.enqueue, article_id, url)
        if result.get("status") == "queued":
            worker_signal.set()
        return result

    @router.get("")
    async def list_saved(
        offset: int = Query(0, ge=0),
        limit: int = Query(60, ge=1, le=200),
        untagged: bool = Query(False),
        tag_prefix: str | None = Query(None, max_length=100),
    ):
        if untagged and tag_prefix:
            raise HTTPException(status_code=400, detail="untagged and tag_prefix are mutually exclusive")
        return await asyncio.to_thread(
            service.list_saved, offset, limit, untagged, tag_prefix
        )

    @router.get("/{save_id}")
    async def get_save(save_id: int):
        result = await asyncio.to_thread(service.get, save_id)
        if result is None:
            raise HTTPException(status_code=404, detail="not found")
        return result

    @router.delete("/{save_id}")
    async def delete_saved(save_id: int):
        ok = await asyncio.to_thread(service.delete_saved, save_id)
        if not ok:
            raise HTTPException(status_code=404, detail="not found")
        return {"deleted": True}

    @router.post("/{save_id}/tags")
    async def add_tag_to_image(save_id: int, payload: dict):
        value = payload.get("value")
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(status_code=400, detail="missing value")
        try:
            tag = await asyncio.to_thread(tag_service.get_or_create, value)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        await asyncio.to_thread(tag_service.assign, save_id, tag.id)
        return {"tag": {"id": tag.id, "value": tag.value}}

    @router.delete("/{save_id}/tags/{tag_id}")
    async def remove_tag_from_image(save_id: int, tag_id: int):
        await asyncio.to_thread(tag_service.unassign, save_id, tag_id)
        return {"removed": True}

    return router
