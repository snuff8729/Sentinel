from __future__ import annotations

import json
import logging
import re

from app.db.engine import get_session
from app.db.models import Article, ArticleVersion, VersionGroup
from app.db.repository import (
    add_article_to_group,
    create_version_group,
    get_or_create_solo_group,
    get_setting,
    search_similar_articles,
    store_embedding,
)
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

        # 가장 유사한 것만 사용
        best_id, best_distance = similar[0]
        best_similarity = 1.0 - best_distance

        with get_session(self._engine) as session:
            best_match = session.get(Article, best_id)
            if not best_match:
                return []

        llm = self._get_llm_client()
        relation = "unknown"
        reason = ""
        group_name = ""

        # LLM 판별 (있으면)
        if llm:
            try:
                prompt = VERSION_CHECK_PROMPT.format(
                    title_a=best_match.title,
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
                logger.warning("[%d] LLM 판별 실패 (%d): %s", article_id, best_id, e)
                relation = "unknown"
                reason = f"LLM 오류: {e}"
        else:
            # LLM 없으면 유사도 기준으로 판단
            if best_similarity >= 0.8:
                relation = "new_version"
                reason = f"유사도 {best_similarity:.0%} (자동)"
            else:
                relation = "possible"
                reason = f"유사도 {best_similarity:.0%} (LLM 미설정)"

        # ArticleVersion 기록
        if relation != "unrelated":
            with get_session(self._engine) as session:
                av = ArticleVersion(
                    article_id=article_id,
                    related_article_id=best_id,
                    relation=relation,
                    confidence=best_similarity,
                    llm_reason=reason,
                )
                session.add(av)
                session.commit()

        # 자동 그룹 연결
        should_auto_link = relation in ("new_version", "same_series") or (relation == "possible" and best_similarity >= 0.8)

        if should_auto_link:
            with get_session(self._engine) as session:
                if best_match.version_group_id:
                    # 기존 그룹에 합류
                    target_group_id = best_match.version_group_id
                    group = session.get(VersionGroup, target_group_id)

                    # 현재 게시글이 solo 그룹에 있으면 삭제
                    current = session.get(Article, article_id)
                    if current and current.version_group_id and current.version_group_id != target_group_id:
                        from app.db.repository import get_articles_in_group, delete_version_group
                        old_articles = get_articles_in_group(session, current.version_group_id)
                        if len(old_articles) <= 1:
                            delete_version_group(session, current.version_group_id)

                    add_article_to_group(session, article_id, target_group_id)
                    logger.info("[%d] → 기존 그룹 '%s'에 자동 연결", article_id, group.name if group else target_group_id)
                else:
                    # 둘 다 그룹 없음 → 새 그룹 생성
                    name = group_name or best_match.title
                    new_group = create_version_group(session, name=name, author=article.author)

                    # 현재 게시글의 solo 그룹 정리
                    current = session.get(Article, article_id)
                    if current and current.version_group_id:
                        from app.db.repository import get_articles_in_group, delete_version_group
                        old_articles = get_articles_in_group(session, current.version_group_id)
                        if len(old_articles) <= 1:
                            delete_version_group(session, current.version_group_id)

                    # 매칭된 게시글의 solo 그룹 정리
                    if best_match.version_group_id:
                        from app.db.repository import get_articles_in_group, delete_version_group
                        old_articles = get_articles_in_group(session, best_match.version_group_id)
                        if len(old_articles) <= 1:
                            delete_version_group(session, best_match.version_group_id)

                    add_article_to_group(session, best_id, new_group.id)
                    add_article_to_group(session, article_id, new_group.id)
                    logger.info("[%d] → 새 그룹 '%s' 생성 + #%d과 묶음", article_id, name, best_id)

        result = {
            "article_id": best_id,
            "title": best_match.title,
            "similarity": round(best_similarity, 3),
            "relation": relation,
            "reason": reason,
            "group_name": group_name,
            "auto_linked": should_auto_link,
        }

        return [result]
