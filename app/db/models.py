from __future__ import annotations
from datetime import datetime
from sqlmodel import Field, SQLModel

class VersionGroup(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str  # 그룹명 (예: "루미나 마을")
    author: str | None = None  # 주 작성자


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
    analysis_status: str = Field(default="none")
    analysis_error: str | None = None
    download_complete: bool = Field(default=False)  # 외부 다운로드 전체 완료 여부
    version_group_id: int | None = Field(default=None, foreign_key="versiongroup.id")
    version_label: str | None = None  # "v1.04", "1.05 업데이트" 등


class FollowedUser(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    note: str | None = None


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


class ArticleVersion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="article.id")
    related_article_id: int = Field(foreign_key="article.id")
    relation: str
    confidence: float = 0.0
    llm_reason: str | None = None


class ArticleLink(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="article.id")
    url: str
    link_type: str
    label: str
    source_article_id: int | None = None
    download_status: str | None = None  # "completed" | "failed" | "manual_required" | None
    download_path: str | None = None
    download_error: str | None = None


class UpdateCheckCache(SQLModel, table=True):
    article_id: int = Field(primary_key=True)
    matched_id: int | None = None
    matched_title: str | None = None
    similarity: float = 0.0
    is_update: bool | None = None
    reason: str = ""
    group_id: int | None = None
    group_name: str | None = None
    checked_at: datetime | None = None


class ArticleFile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="article.id")
    filename: str
    local_path: str
    size: int = 0
    note: str | None = None  # 사용자 메모


class Download(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="article.id")
    url: str
    local_path: str
    file_type: str
    status: str = Field(default="pending")
    error: str | None = None
    warning: str | None = None
