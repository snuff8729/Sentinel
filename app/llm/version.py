from __future__ import annotations

import logging

from app.db.engine import get_session
from app.db.models import Article, ArticleVersion, VersionGroup
from app.db.repository import (
    add_article_to_group,
    create_version_group,
    get_setting,
    search_similar_articles,
    store_embedding,
)
from app.llm.embedding import EmbeddingClient
from sqlmodel import select

logger = logging.getLogger(__name__)


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
        """sqlite-vec로 유사 게시글을 찾고 유사도 기반으로 자동 그룹 연결."""
        with get_session(self._engine) as session:
            article = session.get(Article, article_id)
            if not article:
                return []

        client = self._get_embedding_client()
        if not client:
            return []

        try:
            text = f"{article.author}: {article.title}"
            query_vec = await client.embed(text)
        except Exception as e:
            logger.warning("[%d] 검색용 임베딩 실패: %s", article_id, e)
            return []

        with get_session(self._engine) as session:
            similar = search_similar_articles(session, query_vec, article.author, article_id, limit=5)

        if not similar:
            return []

        # 가장 유사한 것만 사용
        best_id, best_distance = similar[0]
        best_similarity = 1.0 - best_distance

        with get_session(self._engine) as session:
            best_match = session.get(Article, best_id)
            if not best_match:
                return []

        logger.info("[%d] 유사 게시글 발견: #%d (유사도 %.0f%%)", article_id, best_id, best_similarity * 100)

        # 유사도 기반 판단
        if best_similarity >= 0.8:
            relation = "new_version"
            reason = f"유사도 {best_similarity:.0%} (자동)"
        else:
            relation = "possible"
            reason = f"유사도 {best_similarity:.0%}"

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

        # 자동 그룹 연결 (유사도 >= 0.8)
        should_auto_link = best_similarity >= 0.8

        if should_auto_link:
            with get_session(self._engine) as session:
                if best_match.version_group_id:
                    target_group_id = best_match.version_group_id
                    group = session.get(VersionGroup, target_group_id)

                    current = session.get(Article, article_id)
                    if current and current.version_group_id and current.version_group_id != target_group_id:
                        from app.db.repository import get_articles_in_group, delete_version_group
                        old_articles = get_articles_in_group(session, current.version_group_id)
                        if len(old_articles) <= 1:
                            delete_version_group(session, current.version_group_id)

                    add_article_to_group(session, article_id, target_group_id)
                    logger.info("[%d] → 기존 그룹 '%s'에 자동 연결", article_id, group.name if group else target_group_id)
                else:
                    name = best_match.title
                    new_group = create_version_group(session, name=name, author=article.author)

                    current = session.get(Article, article_id)
                    if current and current.version_group_id:
                        from app.db.repository import get_articles_in_group, delete_version_group
                        old_articles = get_articles_in_group(session, current.version_group_id)
                        if len(old_articles) <= 1:
                            delete_version_group(session, current.version_group_id)

                    if best_match.version_group_id:
                        from app.db.repository import get_articles_in_group, delete_version_group
                        old_articles = get_articles_in_group(session, best_match.version_group_id)
                        if len(old_articles) <= 1:
                            delete_version_group(session, best_match.version_group_id)

                    add_article_to_group(session, best_id, new_group.id)
                    add_article_to_group(session, article_id, new_group.id)
                    logger.info("[%d] → 새 그룹 '%s' 생성 + #%d과 묶음", article_id, name, best_id)

        return [{
            "article_id": best_id,
            "title": best_match.title,
            "similarity": round(best_similarity, 3),
            "relation": relation,
            "reason": reason,
            "auto_linked": should_auto_link,
        }]
