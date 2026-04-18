from pathlib import Path

from app.scraper.arca.models import Comment
from app.scraper.arca.parser import parse_comments

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_comments_returns_list():
    html = _load("article_with_comments.html")
    comments = parse_comments(html)
    assert len(comments) > 0
    assert all(isinstance(c, Comment) for c in comments)


def test_comment_has_fields():
    html = _load("article_with_comments.html")
    comments = parse_comments(html)
    c = comments[0]
    assert c.id.startswith("c_")
    assert len(c.author) > 0
    assert c.created_at.year > 2000


def test_comments_have_replies():
    html = _load("article_with_comments.html")
    comments = parse_comments(html)
    has_replies = any(len(c.replies) > 0 for c in comments)
    assert has_replies, "Expected at least one comment with replies"


def test_reply_structure():
    html = _load("article_with_comments.html")
    comments = parse_comments(html)
    for c in comments:
        for r in c.replies:
            assert r.id.startswith("c_")
            assert len(r.author) > 0
            assert r.replies == []  # 대댓글에 또 대댓글 중첩 없음
