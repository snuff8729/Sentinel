from __future__ import annotations

from app.scraper.arca.models import ArticleDetail, ArticleList, Category, ChannelInfo, Comment
from app.scraper.arca.parser import (
    parse_article_detail,
    parse_article_list,
    parse_categories,
    parse_channel_info,
    parse_comments,
    parse_pagination,
)


class ArcaChannel:
    """arca.live 채널 단위 API."""

    def __init__(self, client, slug: str):
        self._client = client
        self._slug = slug

    @property
    def base_path(self) -> str:
        return f"/b/{self._slug}"

    def get_info(self) -> ChannelInfo:
        resp = self._client.get(self.base_path, params={})
        return parse_channel_info(resp.text, self._slug)

    def get_categories(self) -> list[Category]:
        resp = self._client.get(self.base_path, params={})
        return parse_categories(resp.text)

    def get_articles(
        self,
        *,
        category: str | None = None,
        mode: str | None = None,
        sort: str | None = None,
        cut: int | None = None,
        page: int = 1,
    ) -> ArticleList:
        params: dict = {}
        if category is not None:
            params["category"] = category
        if mode is not None:
            params["mode"] = mode
        if sort is not None:
            params["sort"] = sort
        if cut is not None:
            params["cut"] = cut
        params["p"] = page

        resp = self._client.get(self.base_path, params=params)
        articles = parse_article_list(resp.text)
        current_page, total_pages = parse_pagination(resp.text)
        return ArticleList(
            articles=articles,
            current_page=current_page,
            total_pages=total_pages,
        )

    def search(
        self,
        keyword: str,
        *,
        target: str = "all",
        page: int = 1,
    ) -> ArticleList:
        params: dict = {
            "target": target,
            "keyword": keyword,
            "p": page,
        }
        resp = self._client.get(self.base_path, params=params)
        articles = parse_article_list(resp.text)
        current_page, total_pages = parse_pagination(resp.text)
        return ArticleList(
            articles=articles,
            current_page=current_page,
            total_pages=total_pages,
        )

    def get_article(self, article_id: int) -> ArticleDetail:
        resp = self._client.get(f"{self.base_path}/{article_id}")
        return parse_article_detail(resp.text, article_id)

    def get_comments(self, article_id: int) -> list[Comment]:
        resp = self._client.get(f"{self.base_path}/{article_id}")
        return parse_comments(resp.text)
