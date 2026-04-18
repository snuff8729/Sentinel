from pathlib import Path
from sqlmodel import Session, select
from app.db.engine import create_engine_and_tables, get_session

def test_create_engine_creates_db(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine_and_tables(f"sqlite:///{db_path}")
    assert db_path.exists()
    engine.dispose()

def test_get_session_returns_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine_and_tables(f"sqlite:///{db_path}")
    with get_session(engine) as session:
        assert isinstance(session, Session)
    engine.dispose()
