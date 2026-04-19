from __future__ import annotations

import asyncio
import logging

from app.db.engine import get_session
from app.db.repository import (
    delete_links_for_article,
    get_article,
    get_links_for_article,
    save_article_links,
    update_article_analysis,
)
from app.llm.link_classifier import classify_links_auto

logger = logging.getLogger(__name__)


class LinkAnalysisService:
    def __init__(self, engine, arca_client):
        self._engine = engine
        self._arca_client = arca_client

    async def analyze_article(self, article_id: int, channel_slug: str) -> None:
        """도메인 기반 자동 분류 + 같은 작성자 원본 따라가기."""
        with get_session(self._engine) as session:
            update_article_analysis(session, article_id, "pending")
            article = get_article(session, article_id)
            author = article.author if article else ""

        try:
            logger.info("[%d] 링크 분석 시작 (rule-based)...", article_id)
            resp = await asyncio.to_thread(
                self._arca_client.get, f"/b/{channel_slug}/{article_id}"
            )

            result = await classify_links_auto(resp.text, self._arca_client, original_author=author)

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
                        error="다운로드 링크를 자동으로 찾지 못했습니다.")
            else:
                with get_session(self._engine) as session:
                    all_links = get_links_for_article(session, article_id)
                    has_downloads = any(l.link_type == "download" for l in all_links)
                    if has_downloads:
                        update_article_analysis(session, article_id, "completed")
                    else:
                        update_article_analysis(session, article_id, "completed",
                            error="다운로드 링크를 찾지 못했습니다.")

            logger.info("[%d] 링크 분석 완료", article_id)

        except Exception as e:
            logger.error("[%d] 링크 분석 실패: %s", article_id, e)
            with get_session(self._engine) as session:
                update_article_analysis(session, article_id, "failed", error=str(e))
