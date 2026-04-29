from datetime import datetime, timezone

from sqlmodel import Session, select

from app.db.engine import create_engine_and_tables
from app.db.models import ImageTag, SavedImage, Tag
from app.saved.service import SavedImageService
from app.saved.tags import TagService

URL = "https://ac-p3.namu.la/20260428sac/abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789.png?expires=1&key=x"


def _make_service():
    engine = create_engine_and_tables("sqlite:///:memory:")
    calls = []
    service = SavedImageService(engine=engine, data_dir="/tmp/test")
    return service, engine, calls


def test_enqueue_creates_pending_row():
    service, engine, _ = _make_service()
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
    service, engine, _ = _make_service()
    first = service.enqueue(article_id=42, url=URL)
    with Session(engine) as s:
        row = s.get(SavedImage, first["id"])
        row.status = "completed"
        s.add(row)
        s.commit()
    second = service.enqueue(article_id=42, url=URL)
    assert second == {"status": "already_saved", "id": first["id"]}


def test_enqueue_returns_queued_for_pending_row():
    service, _, __ = _make_service()
    first = service.enqueue(article_id=42, url=URL)
    second = service.enqueue(article_id=42, url=URL)
    assert second == {"status": "queued", "id": first["id"]}


def test_enqueue_resets_failed_row_to_pending():
    service, engine, _ = _make_service()
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
    service, _, __ = _make_service()
    result = service.enqueue(article_id=42, url="https://evil.example.com/x.png")
    assert result["status"] == "error"
    assert "host" in result.get("error", "").lower() or "url" in result.get("error", "").lower()


def _seed_completed(engine, article_id=42, hex_id="abc", file_path="saved/42/abc.png", payload=None):
    with Session(engine) as s:
        img = SavedImage(
            article_id=article_id, hex=hex_id,
            src_url="https://ac.namu.la/x.png",
            file_path=file_path,
            payload_json=payload,
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        s.add(img); s.commit(); s.refresh(img)
        return img.id


def test_get_includes_tags():
    service, engine, _ = _make_service()
    img_id = _seed_completed(engine)
    tag_svc = TagService(engine)
    t = tag_svc.get_or_create("foo")
    tag_svc.assign(img_id, t.id)

    result = service.get(img_id)
    assert result is not None
    assert result["tags"] == [{"id": t.id, "value": "foo"}]


def test_list_returns_items_with_tags_and_total():
    service, engine, _ = _make_service()
    img_id = _seed_completed(engine)
    tag_svc = TagService(engine)
    t = tag_svc.get_or_create("bar")
    tag_svc.assign(img_id, t.id)

    result = service.list_saved(offset=0, limit=10)
    assert result["total"] == 1
    assert result["has_more"] is False
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["id"] == img_id
    assert item["tags"] == [{"id": t.id, "value": "bar"}]


def test_list_filter_untagged():
    service, engine, _ = _make_service()
    tagged_id = _seed_completed(engine, hex_id="a")
    untagged_id = _seed_completed(engine, hex_id="b")
    tag_svc = TagService(engine)
    t = tag_svc.get_or_create("foo")
    tag_svc.assign(tagged_id, t.id)

    result = service.list_saved(untagged=True)
    ids = [i["id"] for i in result["items"]]
    assert ids == [untagged_id]


def test_list_filter_tag_prefix():
    service, engine, _ = _make_service()
    a_id = _seed_completed(engine, hex_id="a")
    b_id = _seed_completed(engine, hex_id="b")
    _ = _seed_completed(engine, hex_id="c")
    tag_svc = TagService(engine)
    char_tag = tag_svc.get_or_create("character:miku")
    artist_tag = tag_svc.get_or_create("artist:foo")
    tag_svc.assign(a_id, char_tag.id)
    tag_svc.assign(b_id, artist_tag.id)

    result = service.list_saved(tag_prefix="character:")
    ids = [i["id"] for i in result["items"]]
    assert ids == [a_id]


def test_list_pagination():
    service, engine, _ = _make_service()
    _ = [_seed_completed(engine, hex_id=f"img{i}") for i in range(5)]
    page1 = service.list_saved(offset=0, limit=2)
    assert len(page1["items"]) == 2
    assert page1["has_more"] is True
    page2 = service.list_saved(offset=2, limit=2)
    assert len(page2["items"]) == 2
    page3 = service.list_saved(offset=4, limit=2)
    assert len(page3["items"]) == 1
    assert page3["has_more"] is False


def test_delete_cascades_image_tag_and_files(tmp_path):
    from app.saved.service import SavedImageService
    engine = create_engine_and_tables("sqlite:///:memory:")
    service = SavedImageService(engine=engine, data_dir=str(tmp_path))

    img_dir = tmp_path / "saved" / "42"
    img_dir.mkdir(parents=True)
    (img_dir / "abc.png").write_bytes(b"fake")
    (img_dir / "abc.json").write_text('{"prompt":"x"}', encoding="utf-8")

    img_id = _seed_completed(engine, article_id=42, hex_id="abc", file_path="saved/42/abc.png")
    tag_svc = TagService(engine)
    t = tag_svc.get_or_create("foo")
    tag_svc.assign(img_id, t.id)

    ok = service.delete_saved(img_id)
    assert ok is True

    assert not (img_dir / "abc.png").exists()
    assert not (img_dir / "abc.json").exists()
    assert not img_dir.exists()
    with Session(engine) as s:
        assert s.get(SavedImage, img_id) is None
        assert s.exec(select(ImageTag).where(ImageTag.image_id == img_id)).all() == []
        # tag itself NOT deleted (orphan, Spec 2B will GC)
        assert s.get(Tag, t.id) is not None


def test_delete_returns_false_for_missing():
    service, _, __ = _make_service()
    assert service.delete_saved(99999) is False


def test_list_saved_includes_source_field():
    service, engine, _ = _make_service()
    with Session(engine) as s:
        s.add(SavedImage(
            article_id=42, hex="d" * 64, src_url=URL, file_path="saved/42/d.png",
            status="completed", created_at=datetime.now(timezone.utc), source="article",
        ))
        s.add(SavedImage(
            article_id=0, hex="e" * 64, src_url="", file_path="library/ee/e.png",
            status="completed", created_at=datetime.now(timezone.utc), source="library",
        ))
        s.commit()
    result = service.list_saved(offset=0, limit=10)
    sources = {item["source"] for item in result["items"]}
    assert sources == {"article", "library"}


def test_get_includes_source_field():
    service, engine, _ = _make_service()
    with Session(engine) as s:
        row = SavedImage(
            article_id=0, hex="f" * 64, src_url="", file_path="library/ff/f.png",
            status="completed", created_at=datetime.now(timezone.utc), source="library",
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        rid = row.id
    result = service.get(rid)
    assert result is not None
    assert result["source"] == "library"


def test_queue_snapshot_excludes_library_rows():
    service, engine, _ = _make_service()
    with Session(engine) as s:
        s.add(SavedImage(
            article_id=42, hex="a" * 64, src_url=URL, file_path="saved/42/a.png",
            status="completed", completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc), source="article",
        ))
        s.add(SavedImage(
            article_id=0, hex="b" * 64, src_url="", file_path="library/bb/b.png",
            status="completed", completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc), source="library",
        ))
        s.commit()
    snap = service.queue_snapshot()
    completed_hexes = {r["hex"] for r in snap["recent_completed"]}
    assert "a" * 64 in completed_hexes
    assert "b" * 64 not in completed_hexes
