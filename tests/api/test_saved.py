import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.saved import create_saved_router
from app.db.engine import create_engine_and_tables

GOOD_URL = "https://ac-p3.namu.la/20260428sac/abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789.png?expires=1&key=x"


@pytest.fixture
def client():
    engine = create_engine_and_tables("sqlite:///:memory:")
    signal = asyncio.Event()
    app = FastAPI()
    router = create_saved_router(engine=engine, data_dir="/tmp/test", worker_signal=signal)
    app.include_router(router, prefix="/api/saved-images")
    return TestClient(app), engine, signal


def test_post_returns_queued_for_new(client):
    c, _, signal = client
    r = c.post("/api/saved-images", json={"article_id": 42, "url": GOOD_URL})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    assert isinstance(body["id"], int)
    assert signal.is_set()


def test_post_returns_already_saved_for_completed(client):
    c, engine, _ = client
    first = c.post("/api/saved-images", json={"article_id": 42, "url": GOOD_URL}).json()
    from sqlmodel import Session
    from app.db.models import SavedImage
    with Session(engine) as s:
        row = s.get(SavedImage, first["id"])
        row.status = "completed"
        s.add(row)
        s.commit()
    second = c.post("/api/saved-images", json={"article_id": 42, "url": GOOD_URL}).json()
    assert second == {"status": "already_saved", "id": first["id"]}


def test_post_rejects_missing_payload(client):
    c, _, _ = client
    r = c.post("/api/saved-images", json={"article_id": 42})
    assert r.status_code == 400
    r2 = c.post("/api/saved-images", json={"url": GOOD_URL})
    assert r2.status_code == 400


def test_post_returns_error_for_non_namu_url(client):
    c, _, _ = client
    r = c.post(
        "/api/saved-images",
        json={"article_id": 42, "url": "https://evil.example.com/x.png"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"


def test_get_returns_row(client):
    c, _, _ = client
    posted = c.post("/api/saved-images", json={"article_id": 42, "url": GOOD_URL}).json()
    r = c.get(f"/api/saved-images/{posted['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["article_id"] == 42
    assert body["status"] == "pending"


def test_list_returns_paginated_items_with_tags(client):
    c, engine, _ = client
    from sqlmodel import Session, select
    from datetime import datetime, timezone
    from app.db.models import SavedImage
    from app.saved.tags import TagService

    with Session(engine) as s:
        for hx in ["a", "b"]:
            s.add(SavedImage(
                article_id=42, hex=hx, src_url="https://ac.namu.la/x.png",
                file_path=f"saved/42/{hx}.png", status="completed",
                created_at=datetime.now(timezone.utc),
            ))
        s.commit()
        first_id = s.exec(select(SavedImage.id).order_by(SavedImage.id)).first()
    tag_svc = TagService(engine)
    t = tag_svc.get_or_create("foo")
    tag_svc.assign(first_id, t.id)

    r = c.get("/api/saved-images?offset=0&limit=10")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["has_more"] is False
    assert len(body["items"]) == 2
    by_id = {it["id"]: it for it in body["items"]}
    assert by_id[first_id]["tags"] == [{"id": t.id, "value": "foo"}]


def test_list_untagged_filter(client):
    c, engine, _ = client
    from sqlmodel import Session, select
    from datetime import datetime, timezone
    from app.db.models import SavedImage
    from app.saved.tags import TagService

    with Session(engine) as s:
        for hx in ["a", "b"]:
            s.add(SavedImage(
                article_id=42, hex=hx, src_url="x", file_path=f"saved/42/{hx}.png",
                status="completed", created_at=datetime.now(timezone.utc),
            ))
        s.commit()
        ids = list(s.exec(select(SavedImage.id).order_by(SavedImage.id)).all())
    tag_svc = TagService(engine)
    t = tag_svc.get_or_create("foo")
    tag_svc.assign(ids[0], t.id)

    r = c.get("/api/saved-images?untagged=true")
    body = r.json()
    assert [it["id"] for it in body["items"]] == [ids[1]]


def test_list_tag_prefix_filter(client):
    c, engine, _ = client
    from sqlmodel import Session, select
    from datetime import datetime, timezone
    from app.db.models import SavedImage
    from app.saved.tags import TagService

    with Session(engine) as s:
        for hx in ["a", "b", "c"]:
            s.add(SavedImage(
                article_id=42, hex=hx, src_url="x", file_path=f"saved/42/{hx}.png",
                status="completed", created_at=datetime.now(timezone.utc),
            ))
        s.commit()
        ids = list(s.exec(select(SavedImage.id).order_by(SavedImage.id)).all())
    tag_svc = TagService(engine)
    char = tag_svc.get_or_create("character:miku")
    artist = tag_svc.get_or_create("artist:foo")
    tag_svc.assign(ids[0], char.id)
    tag_svc.assign(ids[1], artist.id)

    r = c.get("/api/saved-images?tag_prefix=character:")
    body = r.json()
    assert [it["id"] for it in body["items"]] == [ids[0]]


def test_list_rejects_untagged_and_prefix_together(client):
    c, _, _ = client
    r = c.get("/api/saved-images?untagged=true&tag_prefix=foo")
    assert r.status_code == 400


def test_delete_endpoint_removes_db_row(client):
    c, engine, _ = client
    from sqlmodel import Session
    from datetime import datetime, timezone
    from app.db.models import SavedImage

    with Session(engine) as s:
        img = SavedImage(
            article_id=42, hex="abc", src_url="x",
            file_path=None,  # no file path → service skips file ops
            status="completed", created_at=datetime.now(timezone.utc),
        )
        s.add(img); s.commit(); s.refresh(img)
        img_id = img.id

    r = c.delete(f"/api/saved-images/{img_id}")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    with Session(engine) as s:
        assert s.get(SavedImage, img_id) is None


def test_delete_endpoint_404_for_missing(client):
    c, _, _ = client
    r = c.delete("/api/saved-images/99999")
    assert r.status_code == 404


def test_post_tag_creates_and_assigns(client):
    c, engine, _ = client
    from sqlmodel import Session, select
    from datetime import datetime, timezone
    from app.db.models import SavedImage, Tag, ImageTag

    with Session(engine) as s:
        img = SavedImage(article_id=42, hex="abc", src_url="x", status="completed",
                         created_at=datetime.now(timezone.utc))
        s.add(img); s.commit(); s.refresh(img); img_id = img.id

    r = c.post(f"/api/saved-images/{img_id}/tags", json={"value": "Character:Miku"})
    assert r.status_code == 200
    body = r.json()
    assert body["tag"]["value"] == "character:miku"
    tag_id = body["tag"]["id"]
    with Session(engine) as s:
        assert s.get(Tag, tag_id).value == "character:miku"
        link = s.exec(select(ImageTag).where(
            ImageTag.image_id == img_id, ImageTag.tag_id == tag_id
        )).first()
        assert link is not None


def test_delete_tag_removes_assignment(client):
    c, engine, _ = client
    from sqlmodel import Session, select
    from datetime import datetime, timezone
    from app.db.models import SavedImage, ImageTag
    from app.saved.tags import TagService

    with Session(engine) as s:
        img = SavedImage(article_id=42, hex="abc", src_url="x", status="completed",
                         created_at=datetime.now(timezone.utc))
        s.add(img); s.commit(); s.refresh(img); img_id = img.id
    tag_svc = TagService(engine)
    t = tag_svc.get_or_create("foo")
    tag_svc.assign(img_id, t.id)

    r = c.delete(f"/api/saved-images/{img_id}/tags/{t.id}")
    assert r.status_code == 200
    with Session(engine) as s:
        link = s.exec(select(ImageTag).where(
            ImageTag.image_id == img_id, ImageTag.tag_id == t.id
        )).first()
    assert link is None


def test_post_tag_rejects_empty(client):
    c, engine, _ = client
    from sqlmodel import Session
    from datetime import datetime, timezone
    from app.db.models import SavedImage

    with Session(engine) as s:
        img = SavedImage(article_id=42, hex="abc", src_url="x", status="completed",
                         created_at=datetime.now(timezone.utc))
        s.add(img); s.commit(); s.refresh(img); img_id = img.id

    r = c.post(f"/api/saved-images/{img_id}/tags", json={"value": "   "})
    assert r.status_code == 400
