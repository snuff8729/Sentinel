from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.api.backup import create_backup_router
from app.backup.events import EventBus
from app.backup.worker import BackupWorker
from app.db.engine import create_engine_and_tables
from app.db.repository import create_article, update_article_status
from sqlmodel import Session


@pytest.fixture
def setup(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    with Session(engine) as session:
        create_article(session, id=1, channel_slug="ch", title="완료됨", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://arca.live/b/ch/1")
        create_article(session, id=2, channel_slug="ch", title="실패함", author="b",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc), url="https://arca.live/b/ch/2")
        update_article_status(session, 1, "completed")
        update_article_status(session, 2, "failed", error="HTTP 404")

    service = MagicMock()
    service._engine = engine
    service.backup_article = AsyncMock()
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)

    test_app = FastAPI()
    router = create_backup_router(worker, event_bus, engine)
    test_app.include_router(router, prefix="/api/backup")
    return TestClient(test_app), engine


def test_history_all(setup):
    client, engine = setup
    resp = client.get("/api/backup/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["page"] == 1
    engine.dispose()


def test_history_by_status(setup):
    client, engine = setup
    resp = client.get("/api/backup/history?status=completed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "완료됨"
    engine.dispose()


def test_history_failed(setup):
    client, engine = setup
    resp = client.get("/api/backup/history?status=failed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["backup_error"] == "HTTP 404"
    engine.dispose()


def test_history_pagination(setup):
    client, engine = setup
    resp = client.get("/api/backup/history?page=1&size=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["size"] == 1
    engine.dispose()


def test_history_sort_title_asc(setup):
    client, engine = setup
    resp = client.get("/api/backup/history?sort=title&dir=asc")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["title"] == "실패함"
    assert items[1]["title"] == "완료됨"
    engine.dispose()


def test_history_categories(setup):
    client, engine = setup
    resp = client.get("/api/backup/history/categories")
    assert resp.status_code == 200
    data = resp.json()
    # 두 article 모두 channel='ch', category=None이라 쌍 하나
    assert len(data) == 1
    assert data[0]["channel_slug"] == "ch"
    assert data[0]["count"] == 2
    engine.dispose()


def test_history_filter_by_channel(setup):
    client, engine = setup
    resp = client.get("/api/backup/history?channel_slug=ch")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2
    resp2 = client.get("/api/backup/history?channel_slug=nonexistent")
    assert resp2.json()["total"] == 0
    engine.dispose()
