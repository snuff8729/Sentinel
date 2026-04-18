from datetime import datetime, timezone
from sqlmodel import Session
from app.db.engine import create_engine_and_tables
from app.db.models import Article, Download
from app.db.repository import (
    create_article, get_article, update_article_status,
    create_download, get_downloads_for_article, update_download_status,
    is_article_completed,
)

def _session(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    return Session(engine)

def test_create_and_get_article(tmp_path):
    with _session(tmp_path) as session:
        art = create_article(session, id=100, channel_slug="test", title="제목", author="작성자",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://arca.live/b/test/100")
        assert art.id == 100
        fetched = get_article(session, 100)
        assert fetched is not None
        assert fetched.title == "제목"

def test_get_article_not_found(tmp_path):
    with _session(tmp_path) as session:
        assert get_article(session, 999) is None

def test_update_article_status(tmp_path):
    with _session(tmp_path) as session:
        create_article(session, id=100, channel_slug="t", title="t", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://arca.live/b/t/100")
        update_article_status(session, 100, "completed")
        art = get_article(session, 100)
        assert art.backup_status == "completed"
        assert art.backed_up_at is not None

def test_update_article_status_failed(tmp_path):
    with _session(tmp_path) as session:
        create_article(session, id=100, channel_slug="t", title="t", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://arca.live/b/t/100")
        update_article_status(session, 100, "failed", error="3 files failed")
        art = get_article(session, 100)
        assert art.backup_status == "failed"
        assert art.backup_error == "3 files failed"

def test_create_and_get_downloads(tmp_path):
    with _session(tmp_path) as session:
        create_article(session, id=100, channel_slug="t", title="t", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://arca.live/b/t/100")
        create_download(session, article_id=100, url="https://x/1.png", local_path="a/1.png", file_type="image")
        create_download(session, article_id=100, url="https://x/2.mp4", local_path="a/2.mp4", file_type="video")
        downloads = get_downloads_for_article(session, 100)
        assert len(downloads) == 2

def test_update_download_status(tmp_path):
    with _session(tmp_path) as session:
        create_article(session, id=100, channel_slug="t", title="t", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://arca.live/b/t/100")
        dl = create_download(session, article_id=100, url="https://x/1.png", local_path="a/1.png", file_type="image")
        update_download_status(session, dl.id, "completed")
        downloads = get_downloads_for_article(session, 100)
        assert downloads[0].status == "completed"

def test_is_article_completed(tmp_path):
    with _session(tmp_path) as session:
        create_article(session, id=100, channel_slug="t", title="t", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://arca.live/b/t/100")
        assert is_article_completed(session, 100) is False
        update_article_status(session, 100, "completed")
        assert is_article_completed(session, 100) is True
