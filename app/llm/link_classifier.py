"""LLM 없이 도메인 기반으로 링크를 분류하고, 원본 게시글을 따라가서 다운로드 링크를 찾는 모듈."""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DOWNLOAD_DOMAINS = {
    "drive.proton.me",
    "realm.risuai.net",
    "chub.ai",
    "mega.nz",
    "catbox.moe",
    "drive.google.com",
    "files.catbox.moe",
}


def _unwrap_unsafelink(url: str) -> str:
    if "unsafelink.com/" in url:
        idx = url.index("unsafelink.com/") + len("unsafelink.com/")
        return url[idx:]
    return url


def _is_download_url(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return any(d in domain for d in DOWNLOAD_DOMAINS)


def _is_arca_url(url: str) -> str | None:
    """arca.live 내부 링크면 (slug, article_id) 반환, 아니면 None."""
    match = re.search(r"arca\.live/b/([^/]+)/(\d+)", url)
    if match:
        return match.group(0)
    return None


def _extract_article_id(url: str) -> int | None:
    match = re.search(r"arca\.live/b/[^/]+/(\d+)", url)
    return int(match.group(1)) if match else None


def _extract_slug(url: str) -> str | None:
    match = re.search(r"arca\.live/b/([^/]+)/", url)
    return match.group(1) if match else None


def extract_links_from_html(html: str) -> list[dict]:
    """게시글 HTML에서 링크를 추출하고 도메인 기반으로 분류.

    Returns: [{"url": str, "type": "download"|"reference"|"other", "label": str, "order": int}]
    """
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".article-body .article-content")
    if not content:
        return []

    links: list[dict] = []
    seen: set[str] = set()

    for i, a in enumerate(content.select("a[href]")):
        href = a.get("href", "")
        if not href or href.startswith("#"):
            continue
        real_url = _unwrap_unsafelink(href)
        if real_url in seen:
            continue
        seen.add(real_url)

        link_text = a.get_text(strip=True) or real_url[:50]

        if _is_download_url(real_url):
            link_type = "download"
        elif _is_arca_url(real_url):
            link_type = "reference"
        else:
            link_type = "other"

        links.append({
            "url": real_url,
            "type": link_type,
            "label": link_text,
            "order": i,
        })

    return links


def get_author_from_html(html: str) -> str:
    """게시글 HTML에서 작성자 추출."""
    soup = BeautifulSoup(html, "lxml")
    author_el = soup.select_one(".article-head .user-info")
    return author_el.get_text(strip=True) if author_el else ""


async def classify_links_auto(html: str, arca_client, original_author: str | None = None) -> dict:
    """도메인 기반 자동 분류 + 원본 따라가기.

    Returns: {
        "links": [...],
        "status": "completed" | "manual_required",
        "followed_from": int | None,  # 따라간 원본 게시글 ID
    }
    """
    links = extract_links_from_html(html)
    if not links:
        return {"links": [], "status": "completed", "followed_from": None}

    author = original_author or get_author_from_html(html)
    download_links = [l for l in links if l["type"] == "download"]

    if download_links:
        return {"links": links, "status": "completed", "followed_from": None}

    # 다운로드 링크 없음 → reference를 위에서부터 순서대로 따라감
    reference_links = sorted(
        [l for l in links if l["type"] == "reference"],
        key=lambda l: l["order"],
    )

    for ref in reference_links:
        ref_id = _extract_article_id(ref["url"])
        ref_slug = _extract_slug(ref["url"])
        if not ref_id or not ref_slug:
            continue

        logger.info("링크 분류: reference 따라감 → %d", ref_id)

        try:
            resp = await asyncio.to_thread(arca_client.get, f"/b/{ref_slug}/{ref_id}")
            ref_author = get_author_from_html(resp.text)

            # 작성자가 다르면 스킵
            if ref_author != author:
                logger.info("링크 분류: %d 작성자 다름 (%s != %s) → 스킵", ref_id, ref_author, author)
                continue

            ref_links = extract_links_from_html(resp.text)
            ref_downloads = [l for l in ref_links if l["type"] == "download"]

            if ref_downloads:
                logger.info("링크 분류: %d에서 다운로드 링크 %d개 발견", ref_id, len(ref_downloads))
                # 원본에서 찾은 다운로드 링크를 현재 게시글 결과에 추가
                for dl in ref_downloads:
                    dl["label"] = f"[원본#{ref_id}] {dl['label']}"
                links.extend(ref_downloads)
                return {"links": links, "status": "completed", "followed_from": ref_id}

        except Exception as e:
            logger.warning("링크 분류: %d 접근 실패: %s", ref_id, e)
            continue

    # 끝까지 못 찾음
    has_unclassified = any(l["type"] == "other" for l in links)
    status = "manual_required" if has_unclassified or not download_links else "completed"
    return {"links": links, "status": "manual_required", "followed_from": None}
