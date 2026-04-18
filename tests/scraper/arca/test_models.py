from datetime import datetime, timezone

from app.scraper.arca.models import (
    ArticleDetail,
    ArticleList,
    ArticleRow,
    Attachment,
    Category,
    Comment,
)


def test_category():
    cat = Category(name="일반", slug="%EC%9D%BC%EB%B0%98")
    assert cat.name == "일반"
    assert cat.slug == "%EC%9D%BC%EB%B0%98"


def test_article_row():
    row = ArticleRow(
        id=599677,
        title="테스트 게시글",
        category="일반",
        comment_count=5,
        author="ㅇㅇ",
        created_at=datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc),
        view_count=100,
        vote_count=10,
        has_image=True,
        has_video=False,
        is_best=False,
        url="https://arca.live/b/characterai/599677",
    )
    assert row.id == 599677
    assert row.has_image is True


def test_article_list():
    al = ArticleList(articles=[], current_page=1, total_pages=10)
    assert al.current_page == 1
    assert al.articles == []


def test_attachment():
    att = Attachment(url="https://ac-p3.namu.la/img.png", media_type="image")
    assert att.media_type == "image"


def test_article_detail():
    detail = ArticleDetail(
        id=168046805,
        title="테스트",
        category="일반",
        author="작성자",
        created_at=datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc),
        view_count=73,
        vote_count=0,
        down_vote_count=0,
        comment_count=0,
        content_html="<p>본문</p>",
        attachments=[],
    )
    assert detail.id == 168046805


def test_comment_with_replies():
    reply = Comment(
        id="c_2",
        author="답글러",
        content_html="<p>답글</p>",
        created_at=datetime(2026, 4, 18, 8, 1, 0, tzinfo=timezone.utc),
    )
    parent = Comment(
        id="c_1",
        author="원댓러",
        content_html="<p>원댓</p>",
        created_at=datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc),
        replies=[reply],
    )
    assert len(parent.replies) == 1
    assert parent.replies[0].id == "c_2"
