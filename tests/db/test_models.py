from datetime import datetime, timezone
from sqlmodel import Session, select
from app.db.engine import create_engine_and_tables
from app.db.models import Article, Download

def _engine(tmp_path):
    return create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")

def test_create_article(tmp_path):
    engine = _engine(tmp_path)
    article = Article(
        id=168039133, channel_slug="characterai", title="테스트 게시글",
        author="Wnfow", category="에셋·모듈봇",
        created_at=datetime(2026, 4, 18, 6, 43, 29, tzinfo=timezone.utc),
        url="https://arca.live/b/characterai/168039133",
    )
    with Session(engine) as session:
        session.add(article)
        session.commit()
        session.refresh(article)
        assert article.id == 168039133
        assert article.backup_status == "pending"
        assert article.backup_error is None
        assert article.backed_up_at is None
    engine.dispose()

def test_create_download(tmp_path):
    engine = _engine(tmp_path)
    article = Article(
        id=168039133, channel_slug="characterai", title="테스트", author="작성자",
        created_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        url="https://arca.live/b/characterai/168039133",
    )
    download = Download(
        article_id=168039133, url="https://ac-p3.namu.la/img.png",
        local_path="articles/168039133/images/img.png", file_type="image",
    )
    with Session(engine) as session:
        session.add(article)
        session.add(download)
        session.commit()
        session.refresh(download)
        assert download.id is not None
        assert download.status == "pending"
        assert download.error is None
    engine.dispose()

def test_article_downloads_relationship(tmp_path):
    engine = _engine(tmp_path)
    article = Article(
        id=100, channel_slug="test", title="t", author="a",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        url="https://arca.live/b/test/100",
    )
    d1 = Download(article_id=100, url="https://x/1.png", local_path="a/1.png", file_type="image")
    d2 = Download(article_id=100, url="https://x/2.mp4", local_path="a/2.mp4", file_type="video")
    with Session(engine) as session:
        session.add(article)
        session.add(d1)
        session.add(d2)
        session.commit()
        result = session.exec(select(Download).where(Download.article_id == 100)).all()
        assert len(result) == 2
        types = {d.file_type for d in result}
        assert types == {"image", "video"}
    engine.dispose()
