from __future__ import annotations
import os
from collections.abc import Generator
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine as sqlmodel_create_engine

load_dotenv()

import app.db.models  # noqa: F401 — registers models with SQLModel.metadata

DEFAULT_DB_URL = "sqlite:///data/sentinel.db"

def create_engine_and_tables(db_url: str | None = None):
    if db_url is None:
        db_url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    engine = sqlmodel_create_engine(db_url, echo=False)
    SQLModel.metadata.create_all(engine)
    return engine

@contextmanager
def get_session(engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
