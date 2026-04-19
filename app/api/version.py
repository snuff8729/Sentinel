from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.engine import get_session
from app.db.repository import (
    add_article_to_group,
    create_version_group,
    delete_version_group,
    get_all_version_groups,
    get_article,
    get_articles_in_group,
    get_version_group,
    remove_article_from_group,
    update_version_group,
)


class CreateGroupRequest(BaseModel):
    name: str
    author: str | None = None


class AddToGroupRequest(BaseModel):
    article_id: int
    version_label: str | None = None


class RenameGroupRequest(BaseModel):
    name: str


def create_version_router(engine) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def list_groups():
        with get_session(engine) as session:
            groups = get_all_version_groups(session)
            result = []
            for g in groups:
                articles = get_articles_in_group(session, g.id)
                result.append({
                    "id": g.id,
                    "name": g.name,
                    "author": g.author,
                    "article_count": len(articles),
                    "articles": [
                        {
                            "id": a.id,
                            "title": a.title,
                            "author": a.author,
                            "version_label": a.version_label,
                            "backup_status": a.backup_status,
                            "created_at": a.created_at.isoformat() if a.created_at else None,
                            "channel_slug": a.channel_slug,
                        }
                        for a in articles
                    ],
                })
            return result

    @router.post("/")
    async def create_group(req: CreateGroupRequest):
        with get_session(engine) as session:
            group = create_version_group(session, req.name, req.author)
            return {"id": group.id, "name": group.name}

    @router.get("/{group_id}")
    async def get_group(group_id: int):
        with get_session(engine) as session:
            group = get_version_group(session, group_id)
            if not group:
                return {"error": "not found"}
            articles = get_articles_in_group(session, group_id)
            return {
                "id": group.id,
                "name": group.name,
                "author": group.author,
                "articles": [
                    {
                        "id": a.id,
                        "title": a.title,
                        "author": a.author,
                        "version_label": a.version_label,
                        "backup_status": a.backup_status,
                        "created_at": a.created_at.isoformat() if a.created_at else None,
                        "channel_slug": a.channel_slug,
                    }
                    for a in articles
                ],
            }

    @router.put("/{group_id}")
    async def rename_group(group_id: int, req: RenameGroupRequest):
        with get_session(engine) as session:
            update_version_group(session, group_id, req.name)
            return {"status": "updated"}

    @router.delete("/{group_id}")
    async def remove_group(group_id: int):
        with get_session(engine) as session:
            delete_version_group(session, group_id)
            return {"status": "deleted"}

    @router.post("/{group_id}/articles")
    async def add_article(group_id: int, req: AddToGroupRequest):
        with get_session(engine) as session:
            # 기존 그룹에서 제거 (1개짜리 solo 그룹이면 삭제)
            article = get_article(session, req.article_id)
            if article and article.version_group_id and article.version_group_id != group_id:
                old_articles = get_articles_in_group(session, article.version_group_id)
                if len(old_articles) <= 1:
                    delete_version_group(session, article.version_group_id)
                else:
                    remove_article_from_group(session, req.article_id)
            add_article_to_group(session, req.article_id, group_id, req.version_label)
            return {"status": "added"}

    @router.delete("/{group_id}/articles/{article_id}")
    async def remove_article(group_id: int, article_id: int):
        with get_session(engine) as session:
            remove_article_from_group(session, article_id)
            # solo 그룹 재생성
            from app.db.repository import get_or_create_solo_group
            get_or_create_solo_group(session, article_id)
            return {"status": "removed"}

    @router.get("/search/{keyword}")
    async def search_groups(keyword: str):
        """그룹명 또는 게시글 제목으로 검색."""
        with get_session(engine) as session:
            groups = get_all_version_groups(session)
            results = []
            for g in groups:
                articles = get_articles_in_group(session, g.id)
                if keyword.lower() in g.name.lower() or any(keyword.lower() in a.title.lower() for a in articles):
                    results.append({
                        "id": g.id,
                        "name": g.name,
                        "author": g.author,
                        "article_count": len(articles),
                    })
            return results

    return router
