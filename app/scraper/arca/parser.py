from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag

from app.scraper.arca.models import (
    ArticleDetail,
    ArticleRow,
    Attachment,
    Category,
    ChannelInfo,
    Comment,
)


# ---------------------------------------------------------------------------
# 게시글 목록
# ---------------------------------------------------------------------------

def parse_article_list(html: str) -> list[ArticleRow]:
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("a.vrow.column")
    articles: list[ArticleRow] = []
    for row in rows:
        classes = row.get("class", [])
        if "notice" in classes or "head" in classes:
            continue
        article = _parse_article_row(row)
        if article:
            articles.append(article)
    return articles


def _parse_article_row(row: Tag) -> ArticleRow | None:
    # 글로벌 ID를 href에서 추출: /b/{slug}/{global_id}?...
    href = row.get("href", "")
    global_id_match = re.search(r"/b/[^/]+/(\d+)", href)
    if not global_id_match:
        return None
    article_id = int(global_id_match.group(1))

    title_el = row.select_one(".col-title .title")
    title = _get_text_with_twemoji(title_el) if title_el else ""

    badge_el = row.select_one(".col-title .badge")
    category = badge_el.get_text(strip=True) if badge_el else None

    comment_el = row.select_one(".col-title .comment-count")
    comment_count = 0
    if comment_el:
        m = re.search(r"\d+", comment_el.get_text())
        if m:
            comment_count = int(m.group())

    author_el = row.select_one(".col-author")
    author = _extract_author(author_el)

    time_el = row.select_one(".col-time time")
    created_at = datetime.min
    if time_el and time_el.get("datetime"):
        created_at = datetime.fromisoformat(
            time_el["datetime"].replace("Z", "+00:00")
        )

    view_count = _parse_int(row.select_one(".col-view"))
    vote_count = _parse_int(row.select_one(".col-rate"))

    has_image = bool(row.select_one(".media-icon.ion-ios-photos-outline"))
    has_video = bool(row.select_one(".media-icon.ion-ios-videocam-outline"))
    is_best = bool(title_el and title_el.select_one(".ion-android-star"))

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
        is_best=is_best,
        url=url,
    )


# ---------------------------------------------------------------------------
# 카테고리 탭
# ---------------------------------------------------------------------------

def parse_channel_info(html: str, slug: str) -> ChannelInfo:
    soup = BeautifulSoup(html, "lxml")
    name_el = soup.select_one(".board-title a.title")
    name = name_el.get("data-channel-name", slug) if name_el else slug
    icon_el = soup.select_one("img.channel-icon")
    icon_url = None
    if icon_el:
        src = icon_el.get("src", "")
        icon_url = f"https:{src}" if src.startswith("//") else src
    return ChannelInfo(slug=slug, name=name, icon_url=icon_url)


def parse_categories(html: str) -> list[Category]:
    soup = BeautifulSoup(html, "lxml")
    cats: list[Category] = []
    for a in soup.select(".board-category a"):
        name = a.get_text(strip=True)
        href = a.get("href", "")
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        slug = qs.get("category", [""])[0]
        cats.append(Category(name=name, slug=slug))
    return cats


# ---------------------------------------------------------------------------
# 페이지네이션
# ---------------------------------------------------------------------------

def parse_pagination(html: str) -> tuple[int, int]:
    """Returns (current_page, total_pages)."""
    soup = BeautifulSoup(html, "lxml")
    pages = soup.select(".pagination-wrapper .pagination a")
    if not pages:
        return 1, 1

    current = 1
    total = 1
    for a in pages:
        href = a.get("href", "")
        qs = parse_qs(urlparse(href).query)
        p_vals = qs.get("p", [])
        if not p_vals:
            continue
        try:
            p = int(p_vals[0])
        except ValueError:
            continue
        if p > total:
            total = p
        if "active" in a.parent.get("class", []):
            current = p

    # active 클래스가 li에 있을 수 있음
    active_li = soup.select_one(".pagination-wrapper .pagination .active a")
    if active_li:
        href = active_li.get("href", "")
        qs = parse_qs(urlparse(href).query)
        p_vals = qs.get("p", [])
        if p_vals:
            try:
                current = int(p_vals[0])
            except ValueError:
                pass

    return current, total


# ---------------------------------------------------------------------------
# 게시글 상세
# ---------------------------------------------------------------------------

def parse_article_detail(html: str, article_id: int) -> ArticleDetail:
    soup = BeautifulSoup(html, "lxml")
    head = soup.select_one(".article-head")

    title_el = head.select_one(".title") if head else None
    title = _get_text_with_twemoji(title_el) if title_el else ""

    badge_el = head.select_one(".badge") if head else None
    category = badge_el.get_text(strip=True) if badge_el else None
    if category and title.startswith(category):
        title = title[len(category):].strip()

    author_el = head.select_one(".user-info") if head else None
    author = _extract_author(author_el)

    info_map: dict[str, str] = {}
    if head:
        heads = head.select(".article-info .head")
        bodies = head.select(".article-info .body")
        for h, b in zip(heads, bodies):
            info_map[h.get_text(strip=True)] = b.get_text(strip=True)

    vote_count = _safe_int(info_map.get("추천", "0"))
    down_vote_count = _safe_int(info_map.get("비추천", "0"))
    comment_count = _safe_int(info_map.get("댓글", "0"))
    view_count = _safe_int(info_map.get("조회수", "0"))

    date_str = info_map.get("작성일", "")
    created_at = datetime.min
    if date_str:
        time_el = head.select_one(".article-info time") if head else None
        if time_el and time_el.get("datetime"):
            created_at = datetime.fromisoformat(
                time_el["datetime"].replace("Z", "+00:00")
            )
        else:
            try:
                created_at = datetime.fromisoformat(date_str)
            except ValueError:
                pass

    content_el = soup.select_one(".article-body .article-content")
    if content_el:
        # protocol-relative URL을 https로 변환 + referrer policy 추가
        for tag in content_el.select("[src]"):
            src = tag.get("src", "")
            if src.startswith("//"):
                tag["src"] = f"https:{src}"
            if tag.name in ("img", "video", "audio"):
                tag["referrerpolicy"] = "no-referrer"
        content_html = content_el.decode_contents()
    else:
        content_html = ""

    attachments: list[Attachment] = []
    article_body = soup.select_one(".article-body")
    search_el = article_body if article_body else content_el
    if search_el:
        for img in search_el.select("img"):
            src = img.get("src", "")
            if not src:
                continue
            if "emoticon" in img.get("class", []):
                continue
            url = f"https:{src}" if src.startswith("//") else src
            attachments.append(Attachment(url=url, media_type="image"))
        for vid in search_el.select("video source, video"):
            src = vid.get("src", "")
            if not src:
                continue
            video_el = vid if vid.name == "video" else vid.parent
            if video_el is not None and "emoticon" in video_el.get("class", []):
                continue
            url = f"https:{src}" if src.startswith("//") else src
            attachments.append(Attachment(url=url, media_type="video"))

    return ArticleDetail(
        id=article_id,
        title=title,
        category=category,
        author=author,
        created_at=created_at,
        view_count=view_count,
        vote_count=vote_count,
        down_vote_count=down_vote_count,
        comment_count=comment_count,
        content_html=content_html,
        attachments=attachments,
    )


# ---------------------------------------------------------------------------
# 댓글
# ---------------------------------------------------------------------------

def parse_comments_html(html: str) -> str:
    """댓글 영역 HTML을 정제하여 반환. 쓰기 폼/신고/답글 버튼 제거."""
    soup = BeautifulSoup(html, "lxml")
    comment_el = soup.select_one("#comment, .article-comment")
    if not comment_el:
        return ""
    # 불필요한 요소 제거
    for el in comment_el.select("form, .reply-form, .btn-arca-article-write, .reply-link, [href*='reports/submit']"):
        el.decompose()
    for btn in comment_el.select(".btn-more"):
        btn.decompose()
    # src 정규화 + referrerpolicy
    for tag in comment_el.select("[src]"):
        src = tag.get("src", "")
        if src.startswith("//"):
            tag["src"] = f"https:{src}"
        if tag.name in ("img", "video", "audio"):
            tag["referrerpolicy"] = "no-referrer"
    return comment_el.decode_contents()


def parse_comments(html: str) -> list[Comment]:
    soup = BeautifulSoup(html, "lxml")
    comments: list[Comment] = []
    for wrapper in soup.select(".comment-wrapper"):
        items = wrapper.select(".comment-item")
        if not items:
            continue
        parent = _parse_comment_item(items[0])
        if not parent:
            continue
        for item in items[1:]:
            reply = _parse_comment_item(item)
            if reply:
                parent.replies.append(reply)
        comments.append(parent)
    return comments


def _parse_comment_item(el: Tag) -> Comment | None:
    comment_id = el.get("id", "")
    if not comment_id:
        return None

    author_el = el.select_one(".user-info")
    author = _extract_author(author_el)

    message_el = el.select_one(".message")
    if message_el:
        for btn in message_el.select(".btn-more"):
            btn.decompose()
        for tag in message_el.select("[src]"):
            src = tag.get("src", "")
            if src.startswith("//"):
                tag["src"] = f"https:{src}"
            if tag.name in ("img", "video", "audio"):
                tag["referrerpolicy"] = "no-referrer"
        content_html = message_el.decode_contents()
    else:
        content_html = ""

    time_el = el.select_one("time")
    created_at = datetime.min
    if time_el and time_el.get("datetime"):
        created_at = datetime.fromisoformat(
            time_el["datetime"].replace("Z", "+00:00")
        )

    return Comment(
        id=comment_id,
        author=author,
        content_html=content_html,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_author(el: Tag | None) -> str:
    """작성자 식별자 추출. 익명(ㅇㅇ)은 data-filter로 고유 ID가 붙어있을 수 있음.
    상세 페이지·댓글: <a data-filter="ㅇㅇ#70481508">ㅇㅇ</a> → "ㅇㅇ#70481508" 반환
    목록: <span data-filter="ㅇㅇ">ㅇㅇ</span> → 번호가 없으므로 "ㅇㅇ" 반환
    일반 유저: data-filter=username → username 반환
    """
    if not el:
        return ""
    tag = el.select_one("[data-filter]")
    if tag:
        val = tag.get("data-filter", "").strip()
        if val:
            return val
    return el.get_text(strip=True)


def _get_text_with_twemoji(el: Tag) -> str:
    """get_text()와 동일하되, twemoji img 태그의 alt 속성을 텍스트로 포함."""
    parts: list[str] = []
    for child in el.descendants:
        if isinstance(child, str):
            parts.append(child)
        elif child.name == "img" and "twemoji" in child.get("class", []):
            alt = child.get("alt", "")
            if alt:
                parts.append(alt)
    return "".join(parts).strip()


def _parse_int(el: Tag | None) -> int:
    if not el:
        return 0
    text = el.get_text(strip=True)
    return _safe_int(text)


def _safe_int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        return 0
