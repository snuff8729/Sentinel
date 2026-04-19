from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.db.engine import get_session
from app.db.models import Article, UpdateCheckCache
from app.db.repository import get_followed_usernames, get_setting, search_similar_articles
from app.llm.embedding import EmbeddingClient
from sqlmodel import select

logger = logging.getLogger(__name__)


class UpdateDetector:
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

    async def check_updates(self, articles: list[dict]) -> list[dict]:
        """게시글 목록에서 팔로우/백업된 유저의 글 중 기존 백업의 업데이트인지 감지."""
        embed_client = self._get_embedding_client()
        if not embed_client:
            return []

        # 1. 대상 필터
        with get_session(self._engine) as session:
            followed = get_followed_usernames(session)
            backed_up_authors = set(
                row[0] for row in session.execute(
                    select(Article.author).where(Article.backup_status == "completed").distinct()
                ).all()
            )

        target_authors = followed | backed_up_authors
        if not target_authors:
            return []

        target_articles = [a for a in articles if a["author"] in target_authors]
        if not target_articles:
            return []

        with get_session(self._engine) as session:
            backed_up_ids = set(
                row[0] for row in session.execute(
                    select(Article.id).where(Article.backup_status == "completed")
                ).all()
            )
        target_articles = [a for a in target_articles if a["id"] not in backed_up_ids]
        if not target_articles:
            return []

        # 캐시 확인
        cached_results: list[dict] = []
        uncached_articles: list[dict] = []
        with get_session(self._engine) as session:
            for a in target_articles:
                cache = session.get(UpdateCheckCache, a["id"])
                if cache and cache.checked_at:
                    if cache.matched_id:
                        cached_results.append({
                            "article_id": cache.article_id,
                            "title": a["title"],
                            "author": a["author"],
                            "matched_id": cache.matched_id,
                            "matched_title": cache.matched_title or "",
                            "similarity": cache.similarity,
                            "is_update": cache.is_update,
                            "reason": cache.reason,
                            "group_id": cache.group_id,
                            "group_name": cache.group_name,
                        })
                else:
                    uncached_articles.append(a)

        if not uncached_articles:
            logger.info("업데이트 감지: 전부 캐시 히트 (%d개)", len(cached_results))
            return cached_results

        target_articles = uncached_articles
        logger.info("업데이트 감지: %d개 게시글 대상 (%d개 캐시)", len(target_articles), len(cached_results))

        # 개별 임베딩 + sqlite-vec 검색
        results: list[dict] = []

        for article in target_articles:
            text = f"{article['author']}: {article['title']}"
            try:
                embedding = await embed_client.embed(text)
            except Exception as e:
                logger.warning("임베딩 실패 (%d): %s", article["id"], e)
                continue

            with get_session(self._engine) as session:
                similar = search_similar_articles(
                    session, embedding, article["author"], article["id"], limit=1
                )
                if not similar:
                    self._save_cache(article["id"], None, None, 0, None, "", None, None)
                    continue

                matched_id, distance = similar[0]
                similarity = 1.0 - distance
                if similarity < 0.7:
                    self._save_cache(article["id"], None, None, 0, None, "", None, None)
                    continue

                matched = session.get(Article, matched_id)
                if not matched:
                    continue

                group_id = matched.version_group_id
                group_name = None
                if group_id:
                    from app.db.models import VersionGroup
                    group = session.get(VersionGroup, group_id)
                    group_name = group.name if group else None

            is_update = similarity >= 0.8
            reason = f"유사도 {similarity:.0%}"

            self._save_cache(article["id"], matched_id, matched.title, similarity,
                             is_update, reason, group_id, group_name)

            if not is_update and similarity < 0.7:
                continue

            results.append({
                "article_id": article["id"],
                "title": article["title"],
                "author": article["author"],
                "matched_id": matched_id,
                "matched_title": matched.title,
                "similarity": round(similarity, 3),
                "is_update": is_update,
                "reason": reason,
                "group_id": group_id,
                "group_name": group_name,
            })

        logger.info("업데이트 감지 결과: %d개 (새 %d + 캐시 %d)", len(results) + len(cached_results), len(results), len(cached_results))
        return cached_results + results

    def _save_cache(self, article_id: int, matched_id: int | None, matched_title: str | None,
                    similarity: float, is_update: bool | None, reason: str,
                    group_id: int | None, group_name: str | None) -> None:
        with get_session(self._engine) as session:
            cache = session.get(UpdateCheckCache, article_id)
            if cache:
                cache.matched_id = matched_id
                cache.matched_title = matched_title
                cache.similarity = similarity
                cache.is_update = is_update
                cache.reason = reason
                cache.group_id = group_id
                cache.group_name = group_name
                cache.checked_at = datetime.now(timezone.utc)
            else:
                cache = UpdateCheckCache(
                    article_id=article_id,
                    matched_id=matched_id,
                    matched_title=matched_title,
                    similarity=similarity,
                    is_update=is_update,
                    reason=reason,
                    group_id=group_id,
                    group_name=group_name,
                    checked_at=datetime.now(timezone.utc),
                )
            session.add(cache)
            session.commit()
