"""POST /api/saved-images { article_id, url } enqueues an image save.
GET /api/saved-images/{id} returns the row state (debug + Spec 2 use).

Service returns error responses with status='error' in the body (200);
HTTP 400 is reserved for malformed payloads (missing article_id/url)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from app.saved.service import SavedImageService


def create_saved_router(engine, data_dir: str, worker_signal: asyncio.Event) -> APIRouter:
    router = APIRouter()
    service = SavedImageService(engine=engine, data_dir=data_dir)

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

    @router.get("/{save_id}")
    async def get_save(save_id: int):
        result = await asyncio.to_thread(service.get, save_id)
        if result is None:
            raise HTTPException(status_code=404, detail="not found")
        return result

    return router
