from pathlib import Path
from unittest.mock import MagicMock

from app.scraper.arca.channel import ArcaChannel
from app.scraper.arca.models import ArticleDetail, ArticleList, Category, Comment

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _mock_client(fixture_name: str) -> MagicMock:
    client = MagicMock()
    resp = MagicMock()
    resp.text = _load(fixture_name)
    client.get.return_value = resp
    return client


def test_get_categories():
    client = _mock_client("article_list.html")
    channel = ArcaChannel(client, "characterai")
    cats = channel.get_categories()
    assert len(cats) > 0
    assert all(isinstance(c, Category) for c in cats)
    client.get.assert_called_once_with("/b/characterai", params={})


def test_get_articles_default():
    client = _mock_client("article_list.html")
    channel = ArcaChannel(client, "characterai")
    result = channel.get_articles()
    assert isinstance(result, ArticleList)
    assert len(result.articles) > 0
    assert result.current_page == 1
    client.get.assert_called_once_with("/b/characterai", params={"p": 1})


def test_get_articles_with_filters():
    client = _mock_client("article_list.html")
    channel = ArcaChannel(client, "characterai")
    channel.get_articles(category="일반", mode="best", sort="reg", cut=10, page=2)
    client.get.assert_called_once_with(
        "/b/characterai",
        params={"category": "일반", "mode": "best", "sort": "reg", "cut": 10, "p": 2},
    )


def test_search():
    client = _mock_client("article_list.html")
    channel = ArcaChannel(client, "characterai")
    result = channel.search(keyword="프롬", target="title", page=1)
    assert isinstance(result, ArticleList)
    client.get.assert_called_once_with(
        "/b/characterai",
        params={"target": "title", "keyword": "프롬", "p": 1},
    )


def test_get_article():
    client = _mock_client("article_detail.html")
    channel = ArcaChannel(client, "characterai")
    detail = channel.get_article(168046805)
    assert isinstance(detail, ArticleDetail)
    assert detail.id == 168046805
    client.get.assert_called_once_with("/b/characterai/168046805")


def test_get_comments():
    client = _mock_client("article_with_comments.html")
    channel = ArcaChannel(client, "characterai")
    comments = channel.get_comments(168046700)
    assert len(comments) > 0
    assert all(isinstance(c, Comment) for c in comments)
    client.get.assert_called_once_with("/b/characterai/168046700")
