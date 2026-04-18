from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup, Tag


@dataclass
class ArticleRow:
    id: int
    title: str
    category: str | None
    comment_count: int
    author: str
    created_at: datetime
    view_count: int
    vote_count: int
    has_image: bool
    has_video: bool
    url: str


def parse_article_list(html: str) -> list[ArticleRow]:
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("a.vrow.column")
    articles: list[ArticleRow] = []

    for row in rows:
        classes = row.get("class", [])
        if "notice" in classes or "head" in classes:
            continue
        article = _parse_row(row)
        if article:
            articles.append(article)

    return articles


def _parse_row(row: Tag) -> ArticleRow | None:
    # ID
    id_el = row.select_one(".col-id")
    if not id_el:
        return None
    try:
        article_id = int(id_el.get_text(strip=True))
    except ValueError:
        return None

    # Title
    title_el = row.select_one(".col-title .title")
    title = title_el.get_text(strip=True) if title_el else ""

    # Category badge
    badge_el = row.select_one(".col-title .badge")
    category = badge_el.get_text(strip=True) if badge_el else None

    # Comment count
    comment_el = row.select_one(".col-title .comment-count")
    comment_count = 0
    if comment_el:
        m = re.search(r"\d+", comment_el.get_text())
        if m:
            comment_count = int(m.group())

    # Author
    author_el = row.select_one(".col-author")
    author = author_el.get_text(strip=True) if author_el else ""

    # Time
    time_el = row.select_one(".col-time time")
    created_at = datetime.min
    if time_el and time_el.get("datetime"):
        created_at = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))

    # View count
    view_el = row.select_one(".col-view")
    view_count = _parse_int(view_el)

    # Vote count
    rate_el = row.select_one(".col-rate")
    vote_count = _parse_int(rate_el)

    # Media indicators
    has_image = bool(row.select_one(".media-icon.ion-ios-photos-outline"))
    has_video = bool(row.select_one(".media-icon.ion-ios-videocam-outline"))

    # URL
    href = row.get("href", "")
    url = href if href.startswith("http") else f"https://arca.live{href}"

    return ArticleRow(
        id=article_id,
        title=title,
        category=category,
        comment_count=comment_count,
        author=author,
        created_at=created_at,
        view_count=view_count,
        vote_count=vote_count,
        has_image=has_image,
        has_video=has_video,
        url=url,
    )


def _parse_int(el: Tag | None) -> int:
    if not el:
        return 0
    text = el.get_text(strip=True)
    try:
        return int(text)
    except ValueError:
        return 0
