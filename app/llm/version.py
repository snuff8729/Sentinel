from __future__ import annotations

import json
import logging
import re

from app.db.engine import get_session
from app.db.models import Article, ArticleVersion
from app.db.repository import get_setting, store_embedding, search_similar_articles
from app.llm.client import LLMClient
from app.llm.embedding import EmbeddingClient
from sqlmodel import select

logger = logging.getLogger(__name__)

VERSION_CHECK_PROMPT = """You are comparing two arca.live post titles from the same author to determine if they are versions of the same content.

Title A (existing): {title_a}
Title B (new): {title_b}
Author: {author}

Classify the relationship and suggest a group name (the common name of the content, without version numbers):
- "new_version": Title B is an updated version of Title A (e.g., v1.0 → v1.5, "update", version number change)
- "same_series": They belong to the same series but are different entries (e.g., different characters, different episodes)
- "unrelated": They are not related

Respond in JSON only:
{{"relation": "new_version"|"same_series"|"unrelated", "reason": "brief explanation in Korean", "group_name": "공통 자료명 (버전 번호 제외)"}}"""


class VersionDetector:
    def __init__(self, engine):
        self._engine = engine

    def _get_embedding_client(self) -> EmbeddingClient | None:
        with get_session(self._engine) as session:
            base_url = get_setting(session, "embedding_base_url")
            if not base_url:
                return None
            return EmbeddingClient(
                base_url=base_url,
                api_key=get_setting(session, "embedding_api_key") or "",
                model=get_setting(session, "embedding_model") or "",
            )

    def _get_llm_client(self) -> LLMClient | None:
        with get_session(self._engine) as session:
            base_url = get_setting(session, "llm_base_url")
            if not base_url:
                return None
            return LLMClient(
                base_url=base_url,
                api_key=get_setting(session, "llm_api_key") or "",
                model=get_setting(session, "llm_model") or "",
            )

    async def generate_embedding(self, article_id: int) -> bool:
        """게시글 제목의 임베딩을 생성하여 sqlite-vec에 저장."""
        client = self._get_embedding_client()
        if not client:
            return False

        with get_session(self._engine) as session:
            article = session.get(Article, article_id)
            if not article:
                return False
            title = article.title
            author = article.author

        try:
            text = f"{author}: {title}"
            vec = await client.embed(text)
            with get_session(self._engine) as session:
                store_embedding(session, article_id, vec)
            logger.info("[%d] 임베딩 생성 완료 (%d차원)", article_id, len(vec))
            return True
        except Exception as e:
            logger.warning("[%d] 임베딩 생성 실패: %s", article_id, e)
            return False

    async def find_related(self, article_id: int) -> list[dict]:
        """sqlite-vec로 유사 게시글을 찾고 LLM으로 관계를 판별."""
        with get_session(self._engine) as session:
            article = session.get(Article, article_id)
            if not article:
                return []

        # 임베딩 재생성하여 검색용으로 사용
        client = self._get_embedding_client()
        if not client:
            return []

        try:
            text = f"{article.author}: {article.title}"
            query_vec = await client.embed(text)
        except Exception as e:
            logger.warning("[%d] 검색용 임베딩 실패: %s", article_id, e)
            return []

        # sqlite-vec로 유사 게시글 검색
        with get_session(self._engine) as session:
            similar = search_similar_articles(session, query_vec, article.author, article_id, limit=5)

        if not similar:
            return []

        logger.info("[%d] 유사 게시글 %d개 발견 (sqlite-vec)", article_id, len(similar))

        # LLM으로 관계 판별
        llm = self._get_llm_client()
        results = []

        for cand_id, distance in similar:
            with get_session(self._engine) as session:
                cand = session.get(Article, cand_id)
                if not cand:
                    continue

            similarity = 1.0 - distance  # distance → similarity
            relation = "unknown"
            reason = ""
            group_name = ""

            if llm:
                try:
                    prompt = VERSION_CHECK_PROMPT.format(
                        title_a=cand.title,
                        title_b=article.title,
                        author=article.author,
                    )
                    response = await llm.chat("You are a helpful assistant.", prompt)
                    json_str = response.strip()
                    if json_str.startswith("```"):
                        json_str = re.sub(r"^```\w*\n?", "", json_str)
                        json_str = re.sub(r"\n?```$", "", json_str)
                    data = json.loads(json_str)
                    relation = data.get("relation", "unknown")
                    reason = data.get("reason", "")
                    group_name = data.get("group_name", "")
                except Exception as e:
                    logger.warning("[%d] LLM 판별 실패 (%d): %s", article_id, cand_id, e)
                    relation = "unknown"
                    reason = f"LLM 오류: {e}"
            else:
                relation = "possible"
                reason = f"유사도 {similarity:.2f} (LLM 미설정)"

            results.append({
                "article_id": cand_id,
                "title": cand.title,
                "similarity": round(similarity, 3),
                "relation": relation,
                "reason": reason,
                "group_name": group_name,
            })

            # DB에 저장 (unrelated 제외)
            if relation != "unrelated":
                with get_session(self._engine) as session:
                    av = ArticleVersion(
                        article_id=article_id,
                        related_article_id=cand_id,
                        relation=relation,
                        confidence=similarity,
                        llm_reason=reason,
                    )
                    session.add(av)
                    session.commit()

        return results
