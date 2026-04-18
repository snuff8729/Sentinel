from __future__ import annotations
from datetime import datetime
from sqlmodel import Field, SQLModel

class Article(SQLModel, table=True):
    id: int = Field(primary_key=True)
    channel_slug: str
    title: str
    author: str
    category: str | None = None
    created_at: datetime
    url: str
    backup_status: str = Field(default="pending")
    backup_error: str | None = None
    backed_up_at: datetime | None = None

class Download(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="article.id")
    url: str
    local_path: str
    file_type: str
    status: str = Field(default="pending")
    error: str | None = None
    warning: str | None = None
