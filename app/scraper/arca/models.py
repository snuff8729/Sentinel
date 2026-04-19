from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ChannelInfo(BaseModel):
    slug: str
    name: str
    icon_url: str | None


class Category(BaseModel):
    name: str
    slug: str


class ArticleRow(BaseModel):
    id: int          # 글로벌 게시글 ID (href에서 추출)
    title: str
    category: str | None
    comment_count: int
    author: str
    created_at: datetime
    view_count: int
    vote_count: int
    has_image: bool
    has_video: bool
    is_best: bool
    url: str
    thumbnail_url: str | None = None


class ArticleList(BaseModel):
    articles: list[ArticleRow]
    current_page: int
    total_pages: int


class Attachment(BaseModel):
    url: str
    media_type: str  # "image" | "video"


class ArticleDetail(BaseModel):
    id: int
    title: str
    category: str | None
    author: str
    created_at: datetime
    view_count: int
    vote_count: int
    down_vote_count: int
    comment_count: int
    content_html: str
    attachments: list[Attachment]


class Comment(BaseModel):
    id: str
    author: str
    content_html: str
    created_at: datetime
    replies: list[Comment] = []
