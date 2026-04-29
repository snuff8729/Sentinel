"""GET /api/tags?prefix=&limit= — autocomplete for tag editor."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from app.saved.tags import TagService


def create_tags_router(engine) -> APIRouter:
    router = APIRouter()
    service = TagService(engine)

    @router.get("")
    async def list_tags(
        prefix: str | None = Query(None, max_length=100),
        limit: int = Query(20, ge=1, le=100),
    ):
        rows = await asyncio.to_thread(service.find_by_prefix, prefix or "", limit)
        return [{"id": r.id, "value": r.value} for r in rows]

    return router
