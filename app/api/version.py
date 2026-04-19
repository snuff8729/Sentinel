from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

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

_SORT_COLUMN = {
    "latest": "latest_at",
    "count": "article_count",
    "name": "vg.name COLLATE NOCASE",
    "author": "vg.author COLLATE NOCASE",
}


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
    async def list_groups(
        page: int = 1,
        size: int = 50,
        sort: str = "latest",
        dir: str = "desc",
        search: str | None = None,
        channel_slug: str | None = None,
        category: str | None = None,
    ):
        """페이지네이션 + 정렬된 그룹 요약 리스트. 게시글은 포함하지 않음.
        channel_slug/category가 지정되면 해당 (channel, category) 조합의 article을 멤버로 가진 그룹만 반환.
        category="" → category IS NULL (카테고리 없음)"""
        size = max(1, min(size, 200))
        page = max(1, page)
        offset = (page - 1) * size
        sort_col = _SORT_COLUMN.get(sort, _SORT_COLUMN["latest"])
        direction = "ASC" if dir.lower() == "asc" else "DESC"
        # NULL을 끝으로 밀기 위해 보조 정렬
        order_clause = f"{sort_col} {direction}, vg.id DESC"

        params: dict = {"limit": size, "offset": offset}
        where_clauses: list[str] = []
        if search:
            where_clauses.append(
                "(vg.name LIKE :kw OR vg.id IN "
                "(SELECT version_group_id FROM article WHERE title LIKE :kw AND version_group_id IS NOT NULL))"
            )
            params["kw"] = f"%{search}%"
        if channel_slug:
            if category is not None and category == "":
                where_clauses.append(
                    "vg.id IN (SELECT version_group_id FROM article "
                    "WHERE channel_slug = :ch AND category IS NULL AND version_group_id IS NOT NULL)"
                )
                params["ch"] = channel_slug
            elif category:
                where_clauses.append(
                    "vg.id IN (SELECT version_group_id FROM article "
                    "WHERE channel_slug = :ch AND category = :cat AND version_group_id IS NOT NULL)"
                )
                params["ch"] = channel_slug
                params["cat"] = category
            else:
                where_clauses.append(
                    "vg.id IN (SELECT version_group_id FROM article "
                    "WHERE channel_slug = :ch AND version_group_id IS NOT NULL)"
                )
                params["ch"] = channel_slug
        where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        with get_session(engine) as session:
            base_sql = f"""
                SELECT vg.id, vg.name, vg.author,
                       COUNT(a.id) AS article_count,
                       MAX(a.created_at) AS latest_at
                FROM versiongroup AS vg
                LEFT JOIN article AS a ON a.version_group_id = vg.id
                {where}
                GROUP BY vg.id
                ORDER BY {order_clause}
                LIMIT :limit OFFSET :offset
            """
            rows = session.execute(text(base_sql), params).fetchall()

            count_sql = f"SELECT COUNT(*) FROM versiongroup AS vg {where}"
            count_params = {k: v for k, v in params.items() if k in ("kw", "ch", "cat")}
            total = session.execute(text(count_sql), count_params).scalar() or 0

            items = [
                {
                    "id": r[0],
                    "name": r[1],
                    "author": r[2],
                    "article_count": r[3],
                    "latest_at": r[4],
                }
                for r in rows
            ]
            return {"items": items, "total": total, "page": page, "size": size}

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
