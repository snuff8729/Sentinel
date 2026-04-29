import pytest
from sqlmodel import Session, select

from app.db.engine import create_engine_and_tables
from app.db.models import ImageTag, SavedImage, Tag
from app.saved.tags import TagService
from datetime import datetime, timezone


def _make():
    engine = create_engine_and_tables("sqlite:///:memory:")
    return TagService(engine), engine


def _seed_image(engine, hex_id="abc"):
    with Session(engine) as s:
        img = SavedImage(
            article_id=1, hex=hex_id, src_url="https://ac.namu.la/x.png",
            status="completed", created_at=datetime.now(timezone.utc),
        )
        s.add(img); s.commit(); s.refresh(img)
        return img.id


def test_get_or_create_creates_new_tag():
    svc, _ = _make()
    t = svc.get_or_create("character:miku")
    assert t.id is not None
    assert t.value == "character:miku"


def test_get_or_create_returns_existing_lowercase():
    svc, engine = _make()
    a = svc.get_or_create("Foo")
    b = svc.get_or_create("FOO")
    c = svc.get_or_create(" foo  ")
    assert a.id == b.id == c.id
    assert a.value == "foo"
    with Session(engine) as s:
        rows = s.exec(select(Tag)).all()
    assert len(rows) == 1


def test_get_or_create_rejects_empty():
    svc, _ = _make()
    with pytest.raises(ValueError):
        svc.get_or_create("")
    with pytest.raises(ValueError):
        svc.get_or_create("   ")


def test_get_or_create_rejects_too_long():
    svc, _ = _make()
    with pytest.raises(ValueError):
        svc.get_or_create("x" * 201)


def test_find_by_prefix_returns_matching_sorted():
    svc, _ = _make()
    svc.get_or_create("character:miku")
    svc.get_or_create("character:rin")
    svc.get_or_create("artist:foo")
    rows = svc.find_by_prefix("character:", 20)
    values = [r.value for r in rows]
    assert values == ["character:miku", "character:rin"]


def test_find_by_prefix_escapes_wildcards():
    svc, _ = _make()
    svc.get_or_create("foo")
    svc.get_or_create("foobar")
    rows = svc.find_by_prefix("foo%", 20)
    assert rows == []


def test_assign_idempotent():
    svc, engine = _make()
    img_id = _seed_image(engine)
    tag = svc.get_or_create("foo")
    svc.assign(img_id, tag.id)
    svc.assign(img_id, tag.id)
    with Session(engine) as s:
        rows = s.exec(select(ImageTag)).all()
    assert len(rows) == 1


def test_unassign_removes_and_noop_when_missing():
    svc, engine = _make()
    img_id = _seed_image(engine)
    tag = svc.get_or_create("foo")
    svc.assign(img_id, tag.id)
    svc.unassign(img_id, tag.id)
    with Session(engine) as s:
        rows = s.exec(select(ImageTag)).all()
    assert rows == []
    svc.unassign(img_id, tag.id)


def test_tags_for_images_batch_returns_grouped():
    svc, engine = _make()
    img1 = _seed_image(engine, hex_id="a")
    img2 = _seed_image(engine, hex_id="b")
    t1 = svc.get_or_create("foo")
    t2 = svc.get_or_create("bar")
    svc.assign(img1, t1.id)
    svc.assign(img1, t2.id)
    svc.assign(img2, t2.id)
    result = svc.tags_for_images([img1, img2])
    assert sorted(t["value"] for t in result[img1]) == ["bar", "foo"]
    assert [t["value"] for t in result[img2]] == ["bar"]
