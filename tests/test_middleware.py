"""Tests for HTTP middlewares."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.middleware import no_cache_on_error


def _make_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(no_cache_on_error)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/missing")
    def missing():
        raise HTTPException(status_code=404, detail="not found")

    @app.get("/server-error")
    def server_error():
        raise HTTPException(status_code=500, detail="boom")

    @app.get("/cached-ok")
    def cached_ok():
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True}, headers={"Cache-Control": "max-age=3600"})

    return app


def test_200_does_not_get_no_store():
    client = TestClient(_make_app())
    r = client.get("/ok")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") != "no-store"


def test_404_gets_no_store():
    client = TestClient(_make_app())
    r = client.get("/missing")
    assert r.status_code == 404
    assert r.headers.get("Cache-Control") == "no-store"


def test_500_gets_no_store():
    client = TestClient(_make_app())
    r = client.get("/server-error")
    assert r.status_code == 500
    assert r.headers.get("Cache-Control") == "no-store"


def test_200_existing_cache_control_preserved():
    client = TestClient(_make_app())
    r = client.get("/cached-ok")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "max-age=3600"
