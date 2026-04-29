from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.tags import create_tags_router
from app.db.engine import create_engine_and_tables
from app.saved.tags import TagService


def _client():
    engine = create_engine_and_tables("sqlite:///:memory:")
    app = FastAPI()
    router = create_tags_router(engine=engine)
    app.include_router(router, prefix="/api/tags")
    return TestClient(app), TagService(engine)


def test_get_tags_no_prefix_returns_all_sorted():
    c, svc = _client()
    svc.get_or_create("zebra")
    svc.get_or_create("apple")
    svc.get_or_create("mango")
    r = c.get("/api/tags")
    assert r.status_code == 200
    values = [t["value"] for t in r.json()]
    assert values == ["apple", "mango", "zebra"]


def test_get_tags_with_prefix_filters():
    c, svc = _client()
    svc.get_or_create("character:miku")
    svc.get_or_create("character:rin")
    svc.get_or_create("artist:foo")
    r = c.get("/api/tags?prefix=character:")
    values = [t["value"] for t in r.json()]
    assert values == ["character:miku", "character:rin"]
