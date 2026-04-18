from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup

from app.llm.client import LLMClient

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """You are a link classifier for arca.live posts (Korean community for AI chatbot assets).

Given a post's text content and links, classify each link into one of these categories:

- "download": Links to download bot cards, assets, modules, or related files. These are usually on proton drive (drive.proton.me), realm (realm.risuai.net), chub (chub.ai), catbox, Google Drive, MEGA, etc.
- "reference": Links to related arca.live posts — original posts, series entries, previous versions, or tools.
- "other": Any other links (documentation, external references, unrelated).

For each link, also provide a short Korean label describing what it is.

Respond in JSON only, no other text:
{
  "links": [
    {"url": "...", "type": "download", "label": "메인 봇카드"},
    {"url": "...", "type": "reference", "label": "원본 게시글"},
    {"url": "...", "type": "other", "label": "참고 문서"}
  ]
}"""


def extract_links_context(html: str) -> str:
    """게시글 HTML에서 텍스트 + 링크 정보를 추출하여 LLM에 보낼 컨텍스트 생성."""
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".article-body .article-content")
    if not content:
        return ""

    # 이미지/비디오 태그 제거 (토큰 절약)
    for tag in content.select("img, video, audio, source"):
        tag.decompose()

    # 텍스트 + 링크 구조 유지
    text = content.get_text(separator="\n", strip=True)

    # 링크 목록
    links = []
    # 다시 파싱 (decompose 이후)
    content2 = BeautifulSoup(html, "lxml").select_one(".article-body .article-content")
    if content2:
        for a in content2.select("a[href]"):
            href = a.get("href", "")
            if not href or href.startswith("#"):
                continue
            link_text = a.get_text(strip=True)
            # unsafelink 래퍼 해제
            real_url = _unwrap_unsafelink(href)
            links.append(f"- [{link_text}]({real_url})")

    if not links:
        return ""

    return f"## 게시글 본문\n{text}\n\n## 링크 목록\n" + "\n".join(links)


def _unwrap_unsafelink(url: str) -> str:
    """unsafelink.com 래퍼를 해제하여 실제 URL 반환."""
    if "unsafelink.com/" in url:
        # https://unsafelink.com/https://real-url
        idx = url.index("unsafelink.com/") + len("unsafelink.com/")
        return url[idx:]
    return url


async def analyze_links(html: str, llm: LLMClient, system_prompt: str | None = None) -> list[dict]:
    """게시글 HTML에서 링크를 추출하고 LLM으로 분류."""
    context = extract_links_context(html)
    if not context:
        return []

    prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    try:
        response = await llm.chat(prompt, context)
        # JSON 파싱 — ```json ... ``` 래핑 처리
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r"^```\w*\n?", "", json_str)
            json_str = re.sub(r"\n?```$", "", json_str)
        data = json.loads(json_str)
        return data.get("links", [])
    except Exception as e:
        logger.error("LLM link analysis failed: %s", e)
        return []
