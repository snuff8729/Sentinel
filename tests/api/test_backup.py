import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.backup import create_backup_router
from app.backup.events import EventBus
from app.backup.worker import BackupWorker


@pytest.fixture
def client():
    service = MagicMock()
    service.backup_article = AsyncMock()
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)

    test_app = FastAPI()
    router = create_backup_router(worker, event_bus, engine=None)
    test_app.include_router(router, prefix="/api/backup")
    return TestClient(test_app)


def test_enqueue_backup(client):
    resp = client.post("/api/backup/test/100")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"


def test_get_queue_status(client):
    resp = client.get("/api/backup/queue")
    assert resp.status_code == 200
    data = resp.json()
    assert "paused" in data
    assert "pending" in data


def test_pause(client):
    resp = client.post("/api/backup/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


def test_resume(client):
    client.post("/api/backup/pause")
    resp = client.post("/api/backup/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resumed"


def test_cancel(client):
    client.post("/api/backup/test/100")
    resp = client.delete("/api/backup/100")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
