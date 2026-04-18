from pathlib import Path

from app.scraper.arca.models import ArticleList, ArticleRow, Category
from app.scraper.arca.parser import parse_article_list, parse_categories, parse_pagination

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_article_list_excludes_notices():
    html = _load("article_list.html")
    articles = parse_article_list(html)
    assert len(articles) > 0
    assert all(isinstance(a, ArticleRow) for a in articles)


def test_parse_article_row_fields():
    html = _load("article_list.html")
    articles = parse_article_list(html)
    a = articles[0]
    assert a.id > 0
    assert len(a.title) > 0
    assert len(a.author) > 0
    assert a.view_count >= 0
    assert a.vote_count >= 0
    assert a.url.startswith("https://arca.live")


def test_parse_categories():
    html = _load("article_list.html")
    cats = parse_categories(html)
    assert len(cats) > 0
    assert all(isinstance(c, Category) for c in cats)
    names = [c.name for c in cats]
    assert "전체" in names


def test_parse_pagination():
    html = _load("article_list.html")
    current, total = parse_pagination(html)
    assert current == 1
    assert total >= 1
