from __future__ import annotations

import json
import logging
import re

from app.db.engine import get_session
from app.db.models import Article, ArticleVersion
from app.db.repository import get_setting
from app.llm.client import LLMClient
from app.llm.embedding import EmbeddingClient, cosine_similarity, embedding_to_json, json_to_embedding
from sqlmodel import select

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.7  # 1차 필터 임계값 (느슨하게)

VERSION_CHECK_PROMPT = """You are comparing two arca.live post titles from the same author to determine if they are versions of the same content.

Title A (existing): {title_a}
Title B (new): {title_b}
Author: {author}

Classify the relationship:
- "new_version": Title B is an updated version of Title A (e.g., v1.0 → v1.5, "update", version number change)
- "same_series": They belong to the same series but are different entries (e.g., different characters, different episodes)
- "unrelated": They are not related

Respond in JSON only:
{{"relation": "new_version"|"same_series"|"unrelated", "reason": "brief explanation in Korean"}}"""


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
        """게시글 제목의 임베딩을 생성하여 DB에 저장."""
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
                article = session.get(Article, article_id)
                if article:
                    article.embedding = embedding_to_json(vec)
                    session.add(article)
                    session.commit()
            logger.info("[%d] 임베딩 생성 완료 (%d차원)", article_id, len(vec))
            return True
        except Exception as e:
            logger.warning("[%d] 임베딩 생성 실패: %s", article_id, e)
            return False

    async def find_related(self, article_id: int) -> list[dict]:
        """같은 작성자의 기존 백업 중 유사한 게시글을 찾고 LLM으로 관계를 판별."""
        with get_session(self._engine) as session:
            article = session.get(Article, article_id)
            if not article or not article.embedding:
                return []

            new_vec = json_to_embedding(article.embedding)

            # 같은 작성자의 기존 백업에서 임베딩이 있는 것만
            stmt = (
                select(Article)
                .where(Article.author == article.author)
                .where(Article.id != article_id)
                .where(Article.embedding.isnot(None))
            )
            candidates = session.exec(stmt).all()

        if not candidates:
            return []

        # 1차: 임베딩 유사도로 후보 추출
        similarities = []
        for cand in candidates:
            cand_vec = json_to_embedding(cand.embedding)
            sim = cosine_similarity(new_vec, cand_vec)
            if sim >= SIMILARITY_THRESHOLD:
                similarities.append((cand, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        top_candidates = similarities[:5]  # 상위 5개만

        if not top_candidates:
            return []

        logger.info("[%d] 유사 게시글 %d개 발견 (임베딩)", article_id, len(top_candidates))

        # 2차: LLM으로 관계 판별
        llm = self._get_llm_client()
        results = []

        for cand, sim in top_candidates:
            relation = "unknown"
            reason = ""

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
                except Exception as e:
                    logger.warning("[%d] LLM 판별 실패 (%d): %s", article_id, cand.id, e)
                    relation = "unknown"
                    reason = f"LLM 오류: {e}"
            else:
                relation = "possible"
                reason = f"유사도 {sim:.2f} (LLM 미설정)"

            results.append({
                "article_id": cand.id,
                "title": cand.title,
                "similarity": round(sim, 3),
                "relation": relation,
                "reason": reason,
            })

            # DB에 저장 (unrelated 제외)
            if relation != "unrelated":
                with get_session(self._engine) as session:
                    av = ArticleVersion(
                        article_id=article_id,
                        related_article_id=cand.id,
                        relation=relation,
                        confidence=sim,
                        llm_reason=reason,
                    )
                    session.add(av)
                    session.commit()

        return results
