import os

from app.scraper.arca.client import ArcaClient


def test_client_with_explicit_cookies():
    client = ArcaClient(cookies="foo=bar; baz=qux")
    assert client.session.cookies.get("foo", domain="arca.live") == "bar"
    assert client.session.cookies.get("baz", domain="arca.live") == "qux"
    client.close()


def test_client_with_empty_cookies():
    client = ArcaClient(cookies="")
    assert client.session is not None
    client.close()


def test_client_loads_from_env(monkeypatch):
    monkeypatch.setenv("ARCA_COOKIES", "envkey=envval; another=thing")
    client = ArcaClient()
    assert client.session.cookies.get("envkey", domain="arca.live") == "envval"
    assert client.session.cookies.get("another", domain="arca.live") == "thing"
    client.close()


def test_client_no_cookies_no_env(monkeypatch):
    monkeypatch.delenv("ARCA_COOKIES", raising=False)
    client = ArcaClient()
    assert client.session is not None
    client.close()
