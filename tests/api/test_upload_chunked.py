from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.backup import create_backup_router
from app.backup.events import EventBus
from app.backup.worker import BackupWorker
from app.db.engine import create_engine_and_tables
from app.db.models import Article


@pytest.fixture
def setup(tmp_path):
    """real engine + tmp data_dir 로 실제 파일/DB 동작 검증."""
    db_path = tmp_path / "test.db"
    engine = create_engine_and_tables(f"sqlite:///{db_path}")

    with Session(engine) as session:
        article = Article(
            id=1,
            channel_slug="test",
            title="t",
            author="",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            url="http://example.com/1",
        )
        session.add(article)
        session.commit()

    service = MagicMock()
    service._data_dir = str(tmp_path)
    service._engine = engine
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)

    test_app = FastAPI()
    router = create_backup_router(worker, event_bus, engine=engine)
    test_app.include_router(router, prefix="/api/backup")
    client = TestClient(test_app)
    return client, tmp_path, engine


def test_init_returns_upload_id_and_creates_uploads_dir(setup):
    client, tmp_path, _ = setup
    resp = client.post("/api/backup/upload-free/init", json={
        "article_id": 1,
        "filename": "hello.txt",
        "total_size": 5,
        "total_chunks": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "upload_id" in data
    assert (tmp_path / ".uploads").is_dir()


def test_init_rejects_total_chunks_mismatch(setup):
    client, _, _ = setup
    # 25MB → 10MB 청크 3개여야 함, 2 로 보내면 거부
    resp = client.post("/api/backup/upload-free/init", json={
        "article_id": 1,
        "filename": "x.bin",
        "total_size": 25 * 1024 * 1024,
        "total_chunks": 2,
    })
    assert resp.status_code == 400


def test_init_rejects_oversized_file(setup):
    client, _, _ = setup
    resp = client.post("/api/backup/upload-free/init", json={
        "article_id": 1,
        "filename": "huge.bin",
        "total_size": 11 * 1024 * 1024 * 1024,  # 11GB > 10GB cap
        "total_chunks": 1126,
    })
    assert resp.status_code == 413
