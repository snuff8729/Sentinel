"""기존 DB article의 author 필드를 최신 식별자 포맷으로 일괄 갱신.

arca.live는 로그인 상태에서 비고정닉/익명 작성자를 'nick#NNN' 형태의 data-filter로 노출함.
예전에 백업된 article들은 그 번호 없이 'ㅇㅇ' 또는 'nick'으로만 저장돼 있어, 서로 다른 사용자가
같은 author로 묶여 버전 그룹핑에 오염을 유발함. 이 스크립트는 각 article 상세를 재조회해
author 값이 변경되었으면 DB에 반영한다.

실행:
    uv run python scripts/refresh_authors.py
    uv run python scripts/refresh_authors.py --delay 2.0 --only-missing-id
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (scripts/에서 직접 실행 시)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

from app.db.engine import create_engine_and_tables
from app.db.models import Article
from app.scraper.arca.client import ArcaClient
from app.scraper.arca.parser import parse_article_detail

logging.basicConfig(level=logging.WARNING, format="%(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay", type=float, default=1.5, help="요청 간 딜레이(초), 기본 1.5")
    parser.add_argument("--only-missing-id", action="store_true",
                        help="author에 '#'이 없는 것만 대상. 기본은 모든 completed 글")
    args = parser.parse_args()

    engine = create_engine_and_tables()
    client = ArcaClient()

    with Session(engine) as session:
        stmt = select(Article).where(Article.backup_status == "completed").order_by(Article.id.asc())
        articles = list(session.exec(stmt).all())

    if args.only_missing_id:
        articles = [a for a in articles if "#" not in a.author]

    total = len(articles)
    updated = unchanged = failed = 0
    print(f"대상 {total}개 article, 딜레이 {args.delay}s")

    for i, art in enumerate(articles, 1):
        try:
            resp = client.get(f"/b/{art.channel_slug}/{art.id}")
            detail = parse_article_detail(resp.text, art.id)
            new_author = detail.author
            if new_author and new_author != art.author:
                with Session(engine) as session:
                    db_art = session.get(Article, art.id)
                    if db_art:
                        db_art.author = new_author
                        session.add(db_art)
                        session.commit()
                updated += 1
                print(f"[{i}/{total}] #{art.id}: {art.author!r} → {new_author!r}")
            else:
                unchanged += 1
                print(f"[{i}/{total}] #{art.id}: 변경 없음 ({art.author!r})")
        except Exception as e:
            failed += 1
            print(f"[{i}/{total}] #{art.id}: 실패 — {e}")

        if i < total:
            time.sleep(args.delay)

    client.close()
    print()
    print(f"완료: 갱신 {updated}, 유지 {unchanged}, 실패 {failed}")


if __name__ == "__main__":
    main()
