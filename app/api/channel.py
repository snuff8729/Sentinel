from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.scraper.arca.channel import ArcaChannel


def create_channel_router(client) -> APIRouter:
    router = APIRouter()

    @router.get("/{slug}/info")
    async def get_info(slug: str):
        channel = ArcaChannel(client, slug)
        info = await asyncio.to_thread(channel.get_info)
        return info.model_dump()

    @router.get("/{slug}/categories")
    async def get_categories(slug: str):
        channel = ArcaChannel(client, slug)
        categories = await asyncio.to_thread(channel.get_categories)
        return [c.model_dump() for c in categories]

    @router.get("/{slug}/articles")
    async def get_articles(
        slug: str,
        category: str | None = None,
        mode: str | None = None,
        sort: str | None = None,
        cut: int | None = None,
        page: int = 1,
    ):
        channel = ArcaChannel(client, slug)
        result = await asyncio.to_thread(
            channel.get_articles,
            category=category,
            mode=mode,
            sort=sort,
            cut=cut,
            page=page,
        )
        return result.model_dump()

    @router.get("/{slug}/search")
    async def search_articles(
        slug: str,
        keyword: str,
        target: str = "all",
        page: int = 1,
    ):
        channel = ArcaChannel(client, slug)
        result = await asyncio.to_thread(
            channel.search,
            keyword,
            target=target,
            page=page,
        )
        return result.model_dump()

    article_router = APIRouter()

    @article_router.get("/{slug}/{article_id}")
    async def get_article(slug: str, article_id: int):
        channel = ArcaChannel(client, slug)
        detail = await asyncio.to_thread(channel.get_article, article_id)
        return detail.model_dump()

    @article_router.get("/{slug}/{article_id}/comments")
    async def get_comments(slug: str, article_id: int):
        channel = ArcaChannel(client, slug)
        comments = await asyncio.to_thread(channel.get_comments, article_id)
        return [c.model_dump() for c in comments]

    router.article_router = article_router
    return router
