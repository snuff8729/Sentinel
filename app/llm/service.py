from __future__ import annotations

import asyncio
import logging
import re

from app.db.engine import get_session
from app.db.repository import (
    delete_links_for_article,
    get_article,
    get_links_for_article,
    get_setting,
    save_article_links,
    update_article_analysis,
)
from app.llm.analyze import analyze_links
from app.llm.client import LLMClient
from app.llm.link_classifier import classify_links_auto

logger = logging.getLogger(__name__)


class LinkAnalysisService:
    def __init__(self, engine, arca_client):
        self._engine = engine
        self._arca_client = arca_client

    def _get_llm(self) -> LLMClient | None:
        with get_session(self._engine) as session:
            base_url = get_setting(session, "llm_base_url")
            if not base_url:
                return None
            return LLMClient(
                base_url=base_url,
                api_key=get_setting(session, "llm_api_key") or "",
                model=get_setting(session, "llm_model") or "",
            )

    def _get_prompt(self) -> str | None:
        with get_session(self._engine) as session:
            return get_setting(session, "llm_prompt") or None

    async def analyze_article(self, article_id: int, channel_slug: str) -> None:
        """게시글 링크를 분석하고 DB에 저장.

        LLM 설정 있으면 → LLM 분석
        LLM 없으면 → 도메인 기반 자동 분류 + 원본 따라가기
        """
        with get_session(self._engine) as session:
            update_article_analysis(session, article_id, "pending")
            article = get_article(session, article_id)
            author = article.author if article else ""

        try:
            logger.info("[%d] 링크 분석 시작...", article_id)
            resp = await asyncio.to_thread(
                self._arca_client.get, f"/b/{channel_slug}/{article_id}"
            )

            llm = self._get_llm()
            if llm:
                await self._analyze_with_llm(article_id, resp.text, llm, author)
            else:
                await self._analyze_with_rules(article_id, resp.text, author)

            logger.info("[%d] 링크 분석 완료", article_id)

        except Exception as e:
            logger.error("[%d] 링크 분석 실패: %s", article_id, e)
            with get_session(self._engine) as session:
                update_article_analysis(session, article_id, "failed", error=str(e))

    async def _analyze_with_llm(self, article_id: int, html: str, llm: LLMClient, author: str) -> None:
        """LLM 기반 분석 + reference 따라가기."""
        prompt = self._get_prompt()
        links = await analyze_links(html, llm, system_prompt=prompt)

        with get_session(self._engine) as session:
            delete_links_for_article(session, article_id)
            save_article_links(session, article_id, links)

        download_links = [l for l in links if l.get("type") == "download"]
        reference_links = [l for l in links if l.get("type") == "reference"]

        if not download_links and reference_links:
            logger.info("[%d] 다운로드 링크 없음 — reference %d개에서 탐색", article_id, len(reference_links))
            for ref in reference_links:
                ref_url = ref.get("url", "")
                ref_match = re.search(r"arca\.live/b/([^/]+)/(\d+)", ref_url)
                if not ref_match:
                    continue
                ref_slug = ref_match.group(1)
                ref_id = int(ref_match.group(2))
                try:
                    ref_resp = await asyncio.to_thread(self._arca_client.get, f"/b/{ref_slug}/{ref_id}")
                    ref_links = await analyze_links(ref_resp.text, llm, system_prompt=prompt)
                    ref_downloads = [l for l in ref_links if l.get("type") == "download"]
                    if ref_downloads:
                        logger.info("[%d] → %d에서 다운로드 링크 %d개 발견", article_id, ref_id, len(ref_downloads))
                        with get_session(self._engine) as session:
                            save_article_links(session, article_id, ref_downloads, source_article_id=ref_id)
                        break
                except Exception as e:
                    logger.warning("[%d] → %d 분석 실패: %s", article_id, ref_id, e)

        self._finalize(article_id)

    async def _analyze_with_rules(self, article_id: int, html: str, author: str) -> None:
        """도메인 기반 자동 분류 + 같은 작성자 원본 따라가기."""
        logger.info("[%d] LLM 미설정 — 도메인 기반 자동 분류", article_id)

        result = await classify_links_auto(html, self._arca_client, original_author=author)

        with get_session(self._engine) as session:
            delete_links_for_article(session, article_id)
            save_article_links(
                session, article_id, result["links"],
                source_article_id=result.get("followed_from"),
            )

        status = result["status"]
        if status == "manual_required":
            with get_session(self._engine) as session:
                update_article_analysis(session, article_id, "manual_required",
                    error="다운로드 링크를 자동으로 찾지 못했습니다. 수동 분류가 필요합니다.")
        else:
            self._finalize(article_id)

    def _finalize(self, article_id: int) -> None:
        """최종 결과 확인 후 상태 업데이트."""
        with get_session(self._engine) as session:
            all_links = get_links_for_article(session, article_id)
            has_downloads = any(l.link_type == "download" for l in all_links)
            if has_downloads:
                update_article_analysis(session, article_id, "completed")
            else:
                update_article_analysis(session, article_id, "completed",
                    error="다운로드 링크를 찾지 못했습니다.")
