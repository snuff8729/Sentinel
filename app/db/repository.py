from __future__ import annotations
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.db.models import Article, Download

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

def create_download(session: Session, *, article_id: int, url: str, local_path: str, file_type: str) -> Download:
    download = Download(article_id=article_id, url=url, local_path=local_path, file_type=file_type)
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

def update_download_status(session: Session, download_id: int, status: str, *, error: str | None = None) -> None:
    download = session.get(Download, download_id)
    if download is None:
        return
    download.status = status
    download.error = error
    session.add(download)
    session.commit()
