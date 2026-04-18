from pathlib import Path

from app.scraper.arca.models import ArticleDetail, Attachment
from app.scraper.arca.parser import parse_article_detail

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_article_detail_meta():
    html = _load("article_detail.html")
    detail = parse_article_detail(html, article_id=168046805)
    assert detail.id == 168046805
    assert len(detail.title) > 0
    assert len(detail.author) > 0
    assert detail.view_count >= 0
    assert detail.vote_count >= 0
    assert detail.down_vote_count >= 0


def test_parse_article_detail_content():
    html = _load("article_detail.html")
    detail = parse_article_detail(html, article_id=168046805)
    assert len(detail.content_html) > 0


def test_parse_article_detail_attachments():
    html = _load("article_detail.html")
    detail = parse_article_detail(html, article_id=168046805)
    images = [a for a in detail.attachments if a.media_type == "image"]
    assert len(images) > 0
    for img in images:
        assert img.url.startswith("https://")


def test_parse_article_detail_excludes_emoticons():
    html = _load("article_detail.html")
    detail = parse_article_detail(html, article_id=168046805)
    for att in detail.attachments:
        assert "arca-emoticon" not in att.url
