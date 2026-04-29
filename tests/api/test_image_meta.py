import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.image_meta import create_image_meta_router
from app.db.engine import create_engine_and_tables

GOOD_URL = "https://ac-p3.namu.la/20260428sac/abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789.png?expires=1&key=x"


@pytest.fixture
def client_factory():
    def _make(fetch_result=b"RIFFxxxxWEBP", parse_result=True):
        engine = create_engine_and_tables("sqlite:///:memory:")
        calls = {"fetch": 0}

        def fake_fetch(url):
            calls["fetch"] += 1
            return fetch_result

        def fake_parse(buf):
            return parse_result

        app = FastAPI()
        router = create_image_meta_router(engine=engine, fetch_fn=fake_fetch, parse_fn=fake_parse)
        app.include_router(router, prefix="/api/image-meta")
        return TestClient(app), calls
    return _make


def test_returns_has_nai_true(client_factory):
    client, _ = client_factory(parse_result=True)
    r = client.get("/api/image-meta", params={"article_id": 42, "url": GOOD_URL})
    assert r.status_code == 200
    assert r.json() == {"has_nai": True, "cached": False}


def test_returns_has_nai_false(client_factory):
    client, _ = client_factory(parse_result=False)
    r = client.get("/api/image-meta", params={"article_id": 42, "url": GOOD_URL})
    assert r.status_code == 200
    assert r.json() == {"has_nai": False, "cached": False}


def test_second_call_returns_cached(client_factory):
    client, calls = client_factory(parse_result=True)
    client.get("/api/image-meta", params={"article_id": 42, "url": GOOD_URL})
    r = client.get("/api/image-meta", params={"article_id": 42, "url": GOOD_URL})
    assert r.json() == {"has_nai": True, "cached": True}
    assert calls["fetch"] == 1


def test_rejects_non_namu_host(client_factory):
    client, calls = client_factory()
    r = client.get(
        "/api/image-meta",
        params={"article_id": 42, "url": "https://evil.example.com/x.png"},
    )
    assert r.status_code == 400
    assert calls["fetch"] == 0


def test_rejects_url_with_dotdot(client_factory):
    client, _ = client_factory()
    r = client.get(
        "/api/image-meta",
        params={"article_id": 42, "url": "https://ac-p3.namu.la/../escape.png"},
    )
    assert r.status_code == 400


def test_rejects_overlong_url(client_factory):
    client, _ = client_factory()
    long_url = "https://ac-p3.namu.la/" + ("a" * 4000) + ".png"
    r = client.get("/api/image-meta", params={"article_id": 42, "url": long_url})
    assert r.status_code == 400


def test_fetch_failure_returns_has_nai_false_and_does_not_cache(client_factory):
    client, calls = client_factory(fetch_result=None)
    r = client.get("/api/image-meta", params={"article_id": 42, "url": GOOD_URL})
    assert r.status_code == 200
    assert r.json() == {"has_nai": False, "cached": False}
    client.get("/api/image-meta", params={"article_id": 42, "url": GOOD_URL})
    assert calls["fetch"] == 2
