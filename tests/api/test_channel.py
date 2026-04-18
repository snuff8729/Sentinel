from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.channel import create_channel_router

FIXTURE_DIR = Path(__file__).parent.parent / "scraper" / "arca" / "fixtures"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def client():
    mock_arca_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = _load("article_list.html")
    mock_arca_client.get.return_value = mock_resp

    test_app = FastAPI()
    router = create_channel_router(mock_arca_client)
    test_app.include_router(router, prefix="/api/channel")
    test_app.include_router(router.article_router, prefix="/api/article")
    return TestClient(test_app), mock_arca_client


def test_get_categories(client):
    test_client, _ = client
    resp = test_client.get("/api/channel/characterai/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert any(c["name"] == "전체" for c in data)


def test_get_articles(client):
    test_client, _ = client
    resp = test_client.get("/api/channel/characterai/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert "articles" in data
    assert "current_page" in data
    assert "total_pages" in data
    assert len(data["articles"]) > 0


def test_get_articles_with_params(client):
    test_client, mock_client = client
    resp = test_client.get("/api/channel/characterai/articles?category=일반&mode=best&page=2")
    assert resp.status_code == 200
    call_args = mock_client.get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("category") == "일반"
    assert params.get("mode") == "best"
    assert params.get("p") == 2


def test_search(client):
    test_client, mock_client = client
    resp = test_client.get("/api/channel/characterai/search?keyword=프롬&target=title")
    assert resp.status_code == 200
    data = resp.json()
    assert "articles" in data


def test_get_article_detail(client):
    test_client, mock_client = client
    detail_html = _load("article_detail.html")
    mock_resp = MagicMock()
    mock_resp.text = detail_html
    mock_client.get.return_value = mock_resp

    resp = test_client.get("/api/article/characterai/168046805")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 168046805
    assert "title" in data
    assert "content_html" in data


def test_get_comments(client):
    test_client, mock_client = client
    comments_html = _load("article_with_comments.html")
    mock_resp = MagicMock()
    mock_resp.text = comments_html
    mock_client.get.return_value = mock_resp

    resp = test_client.get("/api/article/characterai/168046700/comments")
    assert resp.status_code == 200
    data = resp.json()
    assert "html" in data
    assert len(data["html"]) > 0
    assert "comment-item" in data["html"]
