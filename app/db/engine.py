from __future__ import annotations
import os
from collections.abc import Generator
from contextlib import contextmanager
from sqlalchemy import event, text
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine as sqlmodel_create_engine
import sqlite_vec

load_dotenv()

import app.db.models  # noqa: F401 — registers models with SQLModel.metadata

DEFAULT_DB_URL = "sqlite:///data/sentinel.db"

# 임베딩 차원 수 (설정에 따라 변경 가능하지만 기본값)
EMBEDDING_DIM = 768


def create_engine_and_tables(db_url: str | None = None):
    if db_url is None:
        db_url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    # In-memory SQLite must use StaticPool so all threads share the same
    # connection and see the same schema (relevant in tests with asyncio.to_thread).
    if db_url == "sqlite:///:memory:":
        engine = sqlmodel_create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = sqlmodel_create_engine(db_url, echo=False)

    # sqlite-vec 확장 로드
    @event.listens_for(engine, "connect")
    def _load_vec_extension(dbapi_conn, connection_record):
        dbapi_conn.enable_load_extension(True)
        sqlite_vec.load(dbapi_conn)
        dbapi_conn.enable_load_extension(False)

    SQLModel.metadata.create_all(engine)

    # vec0 가상 테이블은 임베딩 설정 시 동적으로 생성
    # (차원 수가 모델마다 다르므로 여기서 고정하지 않음)

    # 자주 조회되는 외래키/필터 컬럼 인덱스 (idempotent)
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_article_version_group_id ON article(version_group_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_article_backup_status ON article(backup_status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_image_meta_cache_article_id ON image_meta_cache(article_id)"))
        conn.commit()

    return engine


@contextmanager
def get_session(engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
