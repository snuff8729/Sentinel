from __future__ import annotations

import logging
import re

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


# 선행 브래킷/괄호 태그 (🔞), [에셋 2080), (04/18UP) 등
_LEADING_TAG_RE = re.compile(r'^\s*(?:[\[\(][^\]\)]{1,40}[\]\)]|[^\s가-힣A-Za-z0-9]+)\s*')
# 선행 orphan 태그: "재배포)", "에셋 2080) " 등 opening 없이 닫힘
_LEADING_ORPHAN_RE = re.compile(r'^[^(\[\n]{1,30}?[\)\]]\s*(?=\S)')
# 꼬리 괄호: (에셋 N개), (변신에셋추가), (매우 작은 업데이트) — 부연 설명
_TRAILING_PAREN_RE = re.compile(r'\s*\([^)]{1,60}\)\s*$')
# 버전 번호: 1.0, v1.1, 2.1v, 1.06버전 (단독 토큰일 때만)
_VERSION_RE = re.compile(r'(?:^|\s)v?\d+(?:\.\d+)+\s*v?(?:버전)?(?=\s|$|,)', re.IGNORECASE)
# 업데이트/출시/리메이크 등 갱신 키워드
_UPDATE_KEYWORDS_RE = re.compile(
    r'\s*(?:정식\s*출시급?|정식\s*출시|출시급|완결의?\s*최종|리메이크|업데이트|업뎃|업뎃됨|업데함|업데이트됨|update)\s*',
    re.IGNORECASE,
)
# 전각/비-한글 기호들 (🔞⛔💐🏫♠️ 등)을 공백으로
_SYMBOLS_RE = re.compile(
    r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\u2000-\u206F\u2100-\u214F\u2190-\u21FF]'
)


def _normalize_title(title: str) -> str:
    """임베딩 품질 향상용: 이모지/태그/버전 접미사/업데이트 키워드 제거.
    원본이 "던전 보스가 되었다 정식 출시급 업데이트" → "던전 보스가 되었다"가 되도록.
    과도 정규화를 피해 핵심 제목만 남기고 안전 측면에서 원문도 fallback으로 사용 가능."""
    t = _SYMBOLS_RE.sub(' ', title)
    # 선행 태그/기호들 최대 3회까지 반복 제거 (opening bracket 있는 형태 + orphan closing)
    for _ in range(3):
        new = _LEADING_TAG_RE.sub('', t, count=1)
        new = _LEADING_ORPHAN_RE.sub('', new, count=1)
        if new == t:
            break
        t = new
    # 버전 번호를 공백으로 (중간에 있어도 제거)
    t = _VERSION_RE.sub(' ', t)
    # 꼬리 괄호와 업데이트 키워드 교대로 반복 제거
    for _ in range(4):
        new = _TRAILING_PAREN_RE.sub('', t)
        new = _UPDATE_KEYWORDS_RE.sub(' ', new)
        if new.strip() == t.strip():
            break
        t = new
    # 공백 정리 + 양쪽 구두점 트림
    t = ' '.join(t.split()).strip(' ,.-:_~!?\'"')
    if t:
        return t
    # 과도 정규화로 비어버리면 심볼만 제거한 버전 사용
    fallback = ' '.join(_SYMBOLS_RE.sub(' ', title).split()).strip()
    return fallback or title


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
            normalized = _normalize_title(title)
            text = f"{author}: {normalized}"
            vec = await client.embed(text)
            with get_session(self._engine) as session:
                store_embedding(session, article_id, vec)
            logger.info("[%d] 임베딩 생성 완료 (%d차원) — '%s'", article_id, len(vec), normalized)
            return True
        except Exception as e:
            logger.warning("[%d] 임베딩 생성 실패: %s", article_id, e)
            return False

    async def find_related(self, article_id: int) -> list[dict]:
        """sqlite-vec로 유사 게시글을 찾고 유사도·그룹 centroid 기반으로 자동 그룹 연결.

        로직:
        - 동일 작가 기준 상위 후보 조회
        - 상위 후보 중 같은 그룹에 2명 이상 있으면 → 그 그룹의 평균 유사도가 GROUP_THRESHOLD 이상일 때 편입
        - 아니면 top-1 유사도가 SINGLE_THRESHOLD 이상일 때 편입 (기존 동작)
        - 현재 글이 이미 멀티-게시글 그룹에 속해 있으면 사용자 지정으로 간주하여 자동 이동 스킵
        """
        SINGLE_THRESHOLD = 0.75  # 같은 작가 기준 완화 (기존 0.8)
        GROUP_THRESHOLD = 0.65   # 그룹 centroid (평균 유사도) 임계값

        with get_session(self._engine) as session:
            article = session.get(Article, article_id)
            if not article:
                return []

        client = self._get_embedding_client()
        if not client:
            return []

        try:
            text = f"{article.author}: {_normalize_title(article.title)}"
            query_vec = await client.embed(text)
        except Exception as e:
            logger.warning("[%d] 검색용 임베딩 실패: %s", article_id, e)
            return []

        with get_session(self._engine) as session:
            similar = search_similar_articles(session, query_vec, article.author, article_id, limit=10)

        if not similar:
            return []

        best_id, best_distance = similar[0]
        best_similarity = 1.0 - best_distance

        with get_session(self._engine) as session:
            best_match = session.get(Article, best_id)
            if not best_match:
                return []

            # 상위 후보를 그룹별로 버킷팅 (centroid 근사용)
            group_buckets: dict[int, list[float]] = {}
            for cand_id, dist in similar:
                cand = session.get(Article, cand_id)
                if cand and cand.version_group_id:
                    group_buckets.setdefault(cand.version_group_id, []).append(1.0 - dist)

            # 후보 그룹 중 ≥2명이 상위에 잡힌 그룹의 평균 유사도 계산
            best_group_id = None
            best_group_sim = 0.0
            for gid, sims in group_buckets.items():
                if len(sims) < 2:
                    continue
                avg = sum(sims) / len(sims)
                if avg > best_group_sim:
                    best_group_sim = avg
                    best_group_id = gid

        logger.info(
            "[%d] 유사 게시글: top #%d=%.0f%%, 후보 그룹 #%s avg=%.0f%%",
            article_id, best_id, best_similarity * 100,
            best_group_id or "-", best_group_sim * 100,
        )

        # 현재 글이 멀티-게시글 그룹에 이미 속해 있으면 수동 지정으로 보고 자동 이동 금지
        with get_session(self._engine) as session:
            current = session.get(Article, article_id)
            current_group_id = current.version_group_id if current else None
            current_group_size = 0
            if current_group_id:
                from app.db.repository import get_articles_in_group
                current_group_size = len(get_articles_in_group(session, current_group_id))

        user_managed = current_group_size >= 2

        # 연결 대상 결정
        target_group_id: int | None = None
        target_reason = ""
        use_centroid = best_group_sim >= GROUP_THRESHOLD and best_group_id is not None
        use_single = best_similarity >= SINGLE_THRESHOLD

        if not user_managed:
            # centroid 시그널은 여러 멤버가 동의하는 매치라 단일보다 신뢰도 높음 → 임계값 넘으면 항상 우선
            if use_centroid:
                target_group_id = best_group_id
                target_reason = f"그룹 평균 유사도 {best_group_sim:.0%}"
            elif use_single:
                target_group_id = best_match.version_group_id  # None이면 아래에서 solo→new group 생성
                target_reason = f"유사도 {best_similarity:.0%}"

        relation = "new_version" if (target_group_id is not None or use_single) else "possible"
        reason = target_reason or f"유사도 {best_similarity:.0%}"

        # ArticleVersion 기록 (가장 유사한 단일 게시글과의 관계)
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

        auto_linked = False
        if not user_managed and (use_centroid or use_single):
            with get_session(self._engine) as session:
                if target_group_id is not None:
                    # 기존 그룹에 편입
                    group = session.get(VersionGroup, target_group_id)
                    if current_group_id and current_group_id != target_group_id:
                        # 현재 solo 그룹이면 정리
                        from app.db.repository import get_articles_in_group, delete_version_group
                        old = get_articles_in_group(session, current_group_id)
                        if len(old) <= 1:
                            delete_version_group(session, current_group_id)
                    add_article_to_group(session, article_id, target_group_id)
                    auto_linked = True
                    logger.info("[%d] → 그룹 '%s'에 자동 편입 (%s)", article_id, group.name if group else target_group_id, reason)
                elif use_single:
                    # best_match가 solo 상태 → 새 그룹 만들고 둘 다 편입
                    name = best_match.title
                    new_group = create_version_group(session, name=name, author=article.author)
                    from app.db.repository import get_articles_in_group, delete_version_group
                    if current_group_id:
                        old = get_articles_in_group(session, current_group_id)
                        if len(old) <= 1:
                            delete_version_group(session, current_group_id)
                    if best_match.version_group_id:
                        old = get_articles_in_group(session, best_match.version_group_id)
                        if len(old) <= 1:
                            delete_version_group(session, best_match.version_group_id)
                    add_article_to_group(session, best_id, new_group.id)
                    add_article_to_group(session, article_id, new_group.id)
                    auto_linked = True
                    logger.info("[%d] → 새 그룹 '%s' 생성 + #%d과 묶음", article_id, name, best_id)
        elif user_managed:
            logger.info("[%d] → 이미 사용자 지정 그룹(%d개)에 속해 있어 자동 연결 스킵", article_id, current_group_size)

        return [{
            "article_id": best_id,
            "title": best_match.title,
            "similarity": round(best_similarity, 3),
            "group_avg_similarity": round(best_group_sim, 3) if best_group_id else None,
            "relation": relation,
            "reason": reason,
            "auto_linked": auto_linked,
        }]

    async def find_candidates(self, article_id: int, min_similarity: float = 0.5, max_similarity: float = 0.8, limit: int = 10) -> list[dict]:
        """수동 승인용: 유사도 중간 구간(0.5~0.8)의 관련 게시글 후보 리턴.
        같은 그룹에 이미 있는 건 제외. 자동 연결은 하지 않음."""
        with get_session(self._engine) as session:
            article = session.get(Article, article_id)
            if not article:
                return []
            current_group_id = article.version_group_id

        client = self._get_embedding_client()
        if not client:
            return []

        try:
            query_vec = await client.embed(f"{article.author}: {_normalize_title(article.title)}")
        except Exception as e:
            logger.warning("[%d] 후보 검색 임베딩 실패: %s", article_id, e)
            return []

        with get_session(self._engine) as session:
            similar = search_similar_articles(session, query_vec, article.author, article_id, limit=limit * 2)

        candidates: list[dict] = []
        with get_session(self._engine) as session:
            for cand_id, distance in similar:
                sim = 1.0 - distance
                if sim < min_similarity or sim > max_similarity:
                    continue
                cand = session.get(Article, cand_id)
                if not cand:
                    continue
                if current_group_id and cand.version_group_id == current_group_id:
                    continue  # 이미 같은 그룹
                group_name = None
                if cand.version_group_id:
                    g = session.get(VersionGroup, cand.version_group_id)
                    group_name = g.name if g else None
                candidates.append({
                    "article_id": cand_id,
                    "title": cand.title,
                    "similarity": round(sim, 3),
                    "group_id": cand.version_group_id,
                    "group_name": group_name,
                })
                if len(candidates) >= limit:
                    break
        return candidates
