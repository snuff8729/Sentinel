from __future__ import annotations
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.db.models import Article, ArticleLink, Download, FollowedUser, Setting

def create_article(session: Session, *, id: int, channel_slug: str, title: str, author: str,
    created_at: datetime, url: str, category: str | None = None) -> Article:
    article = Article(id=id, channel_slug=channel_slug, title=title, author=author,
        category=category, created_at=created_at, url=url)
    session.add(article)
    session.commit()
    session.refresh(article)
    return article

def get_article(session: Session, article_id: int) -> Article | None:
    return session.get(Article, article_id)

def update_article_status(session: Session, article_id: int, status: str, *, error: str | None = None) -> None:
    article = session.get(Article, article_id)
    if article is None:
        return
    article.backup_status = status
    article.backup_error = error
    if status == "completed":
        article.backed_up_at = datetime.now(timezone.utc)
    session.add(article)
    session.commit()

def is_article_completed(session: Session, article_id: int) -> bool:
    article = session.get(Article, article_id)
    if article is None:
        return False
    return article.backup_status == "completed"

def create_download(session: Session, *, article_id: int, url: str, local_path: str, file_type: str, warning: str | None = None) -> Download:
    download = Download(article_id=article_id, url=url, local_path=local_path, file_type=file_type, warning=warning)
    session.add(download)
    session.commit()
    session.refresh(download)
    return download

def get_articles_by_status(session: Session, status: str | None = None) -> list[Article]:
    if status:
        statement = select(Article).where(Article.backup_status == status).order_by(Article.id.desc())
    else:
        statement = select(Article).order_by(Article.id.desc())
    return list(session.exec(statement).all())

def get_downloads_for_article(session: Session, article_id: int) -> list[Download]:
    statement = select(Download).where(Download.article_id == article_id)
    return list(session.exec(statement).all())


def delete_downloads_for_article(session: Session, article_id: int) -> None:
    downloads = get_downloads_for_article(session, article_id)
    for dl in downloads:
        session.delete(dl)
    session.commit()

def update_download_status(session: Session, download_id: int, status: str, *, error: str | None = None) -> None:
    download = session.get(Download, download_id)
    if download is None:
        return
    download.status = status
    download.error = error
    session.add(download)
    session.commit()


def get_links_for_article(session: Session, article_id: int) -> list[ArticleLink]:
    statement = select(ArticleLink).where(ArticleLink.article_id == article_id)
    return list(session.exec(statement).all())


def save_article_links(session: Session, article_id: int, links: list[dict], source_article_id: int | None = None) -> None:
    for link in links:
        al = ArticleLink(
            article_id=article_id,
            url=link["url"],
            link_type=link.get("type", "other"),
            label=link.get("label", ""),
            source_article_id=source_article_id,
        )
        session.add(al)
    session.commit()


def delete_links_for_article(session: Session, article_id: int) -> None:
    links = get_links_for_article(session, article_id)
    for link in links:
        session.delete(link)
    session.commit()


def update_article_analysis(session: Session, article_id: int, status: str, *, error: str | None = None) -> None:
    article = session.get(Article, article_id)
    if article is None:
        return
    article.analysis_status = status
    article.analysis_error = error
    session.add(article)
    session.commit()


def follow_user(session: Session, username: str, note: str | None = None) -> FollowedUser:
    existing = session.exec(select(FollowedUser).where(FollowedUser.username == username)).first()
    if existing:
        if note is not None:
            existing.note = note
            session.add(existing)
            session.commit()
        return existing
    fu = FollowedUser(username=username, note=note)
    session.add(fu)
    session.commit()
    session.refresh(fu)
    return fu


def unfollow_user(session: Session, username: str) -> None:
    existing = session.exec(select(FollowedUser).where(FollowedUser.username == username)).first()
    if existing:
        session.delete(existing)
        session.commit()


def get_followed_users(session: Session) -> list[FollowedUser]:
    return list(session.exec(select(FollowedUser)).all())


def is_followed(session: Session, username: str) -> bool:
    return session.exec(select(FollowedUser).where(FollowedUser.username == username)).first() is not None


def get_followed_usernames(session: Session) -> set[str]:
    users = session.exec(select(FollowedUser)).all()
    return {u.username for u in users}


def store_embedding(session: Session, article_id: int, embedding: list[float]) -> None:
    import json
    from sqlalchemy import text
    dim = len(embedding)
    vec_json = json.dumps(embedding)
    # 가상 테이블이 없으면 생성
    session.execute(text(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS article_vec USING vec0(article_id INTEGER PRIMARY KEY, embedding float[{dim}])"
    ))
    # upsert: delete + insert
    session.execute(text("DELETE FROM article_vec WHERE article_id = :id"), {"id": article_id})
    session.execute(
        text("INSERT INTO article_vec (article_id, embedding) VALUES (:id, :vec)"),
        {"id": article_id, "vec": vec_json},
    )
    session.commit()


def search_similar_articles(session: Session, embedding: list[float], author: str, exclude_id: int, limit: int = 5) -> list[tuple[int, float]]:
    """임베딩 유사도로 같은 작성자의 유사 게시글 검색. (article_id, distance) 리스트 반환."""
    import json
    from sqlalchemy import text
    vec_json = json.dumps(embedding)
    # article_vec에서 KNN 검색 후 author 필터 (join)
    results = session.execute(
        text("""
            SELECT av.article_id, av.distance
            FROM article_vec AS av
            JOIN article ON article.id = av.article_id
            WHERE av.embedding MATCH :vec
              AND av.k = :limit_k
              AND article.author = :author
              AND av.article_id != :exclude_id
            ORDER BY av.distance
            LIMIT :limit_n
        """),
        {"vec": vec_json, "limit_k": limit * 5, "author": author, "exclude_id": exclude_id, "limit_n": limit},
    ).fetchall()
    return [(row[0], row[1]) for row in results]


def get_setting(session: Session, key: str) -> str | None:
    setting = session.get(Setting, key)
    return setting.value if setting else None


def set_setting(session: Session, key: str, value: str) -> None:
    setting = session.get(Setting, key)
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
    session.add(setting)
    session.commit()


def get_all_settings(session: Session, prefix: str = "") -> dict[str, str]:
    statement = select(Setting)
    settings = session.exec(statement).all()
    return {s.key: s.value for s in settings if s.key.startswith(prefix)}
