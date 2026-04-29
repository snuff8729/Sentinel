import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.saved import create_saved_router
from app.db.engine import create_engine_and_tables

GOOD_URL = "https://ac-p3.namu.la/20260428sac/abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789.png?expires=1&key=x"


@pytest.fixture
def client():
    engine = create_engine_and_tables("sqlite:///:memory:")
    signal = asyncio.Event()
    app = FastAPI()
    router = create_saved_router(engine=engine, data_dir="/tmp/test", worker_signal=signal)
    app.include_router(router, prefix="/api/saved-images")
    return TestClient(app), engine, signal


def test_post_returns_queued_for_new(client):
    c, _, signal = client
    r = c.post("/api/saved-images", json={"article_id": 42, "url": GOOD_URL})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    assert isinstance(body["id"], int)
    assert signal.is_set()


def test_post_returns_already_saved_for_completed(client):
    c, engine, _ = client
    first = c.post("/api/saved-images", json={"article_id": 42, "url": GOOD_URL}).json()
    from sqlmodel import Session
    from app.db.models import SavedImage
    with Session(engine) as s:
        row = s.get(SavedImage, first["id"])
        row.status = "completed"
        s.add(row)
        s.commit()
    second = c.post("/api/saved-images", json={"article_id": 42, "url": GOOD_URL}).json()
    assert second == {"status": "already_saved", "id": first["id"]}


def test_post_rejects_missing_payload(client):
    c, _, _ = client
    r = c.post("/api/saved-images", json={"article_id": 42})
    assert r.status_code == 400
    r2 = c.post("/api/saved-images", json={"url": GOOD_URL})
    assert r2.status_code == 400


def test_post_returns_error_for_non_namu_url(client):
    c, _, _ = client
    r = c.post(
        "/api/saved-images",
        json={"article_id": 42, "url": "https://evil.example.com/x.png"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"


def test_get_returns_row(client):
    c, _, _ = client
    posted = c.post("/api/saved-images", json={"article_id": 42, "url": GOOD_URL}).json()
    r = c.get(f"/api/saved-images/{posted['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["article_id"] == 42
    assert body["status"] == "pending"
