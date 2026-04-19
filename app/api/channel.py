from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.scraper.arca.channel import ArcaChannel
from app.scraper.arca.parser import parse_comments_html


def create_channel_router(client, engine=None) -> APIRouter:
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
        category: str | None = None,
        mode: str | None = None,
        page: int = 1,
    ):
        channel = ArcaChannel(client, slug)
        result = await asyncio.to_thread(
            channel.search,
            keyword,
            target=target,
            category=category,
            mode=mode,
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
        resp = await asyncio.to_thread(client.get, f"/b/{slug}/{article_id}")
        comments_html = parse_comments_html(resp.text)
        return {"html": comments_html}

    @article_router.post("/{slug}/{article_id}/analyze-links")
    async def analyze_article_links(slug: str, article_id: int):
        from app.db.engine import get_session
        from app.db.repository import get_setting
        from app.llm.client import LLMClient
        from app.llm.analyze import analyze_links

        _engine = engine
        if not _engine:
            return {"error": "engine not configured", "links": []}

        with get_session(_engine) as session:
            base_url = get_setting(session, "llm_base_url")
            api_key = get_setting(session, "llm_api_key") or ""
            model = get_setting(session, "llm_model") or ""
            system_prompt = get_setting(session, "llm_prompt") or None

        if not base_url:
            return {"error": "LLM이 설정되지 않았습니다. 설정 페이지에서 구성해주세요.", "links": []}

        resp = await asyncio.to_thread(client.get, f"/b/{slug}/{article_id}")
        llm = LLMClient(base_url=base_url, api_key=api_key, model=model)
        links = await analyze_links(resp.text, llm, system_prompt=system_prompt)
        return {"links": links}

    router.article_router = article_router
    return router
