from sqlmodel import Session, select

from app.db.engine import create_engine_and_tables
from app.db.models import SavedImage
from app.saved.service import SavedImageService

URL = "https://ac-p3.namu.la/20260428sac/abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789.png?expires=1&key=x"


def _make_service():
    engine = create_engine_and_tables("sqlite:///:memory:")
    service = SavedImageService(engine=engine, data_dir="/tmp/test")
    return service, engine


def test_enqueue_creates_pending_row():
    service, engine = _make_service()
    result = service.enqueue(article_id=42, url=URL)
    assert result["status"] == "queued"
    assert isinstance(result["id"], int)

    with Session(engine) as s:
        rows = s.exec(select(SavedImage)).all()
    assert len(rows) == 1
    assert rows[0].article_id == 42
    assert rows[0].status == "pending"
    assert rows[0].retry_count == 0
    assert rows[0].src_url == URL


def test_enqueue_returns_already_saved_for_completed_row():
    service, engine = _make_service()
    first = service.enqueue(article_id=42, url=URL)
    with Session(engine) as s:
        row = s.get(SavedImage, first["id"])
        row.status = "completed"
        s.add(row)
        s.commit()
    second = service.enqueue(article_id=42, url=URL)
    assert second == {"status": "already_saved", "id": first["id"]}


def test_enqueue_returns_queued_for_pending_row():
    service, _ = _make_service()
    first = service.enqueue(article_id=42, url=URL)
    second = service.enqueue(article_id=42, url=URL)
    assert second == {"status": "queued", "id": first["id"]}


def test_enqueue_resets_failed_row_to_pending():
    service, engine = _make_service()
    first = service.enqueue(article_id=42, url=URL)
    with Session(engine) as s:
        row = s.get(SavedImage, first["id"])
        row.status = "failed"
        row.retry_count = 3
        row.error = "old error"
        s.add(row)
        s.commit()
    second = service.enqueue(article_id=42, url=URL)
    assert second == {"status": "queued", "id": first["id"]}
    with Session(engine) as s:
        row = s.get(SavedImage, first["id"])
    assert row.status == "pending"
    assert row.retry_count == 0
    assert row.error is None


def test_enqueue_rejects_non_namu_url():
    service, _ = _make_service()
    result = service.enqueue(article_id=42, url="https://evil.example.com/x.png")
    assert result["status"] == "error"
    assert "host" in result.get("error", "").lower() or "url" in result.get("error", "").lower()
