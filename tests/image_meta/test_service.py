import json as _j
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.db.engine import create_engine_and_tables
from app.db.models import ImageMetaCache
from app.image_meta.service import ImageMetaService, _make_key

URL = "https://ac-p3.namu.la/20260428sac/abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789.png?expires=1&key=x"


def _make_service(fetch_returns=b"RIFF\x00\x00\x00\x00WEBP", parse_result=None):
    """parse_result: dict (NAI), None (not NAI). Bool no longer accepted."""
    engine = create_engine_and_tables("sqlite:///:memory:")
    calls = {"fetch": 0, "parse": 0}

    def fake_fetch(url: str) -> bytes | None:
        calls["fetch"] += 1
        return fetch_returns

    def fake_parse(buf: bytes) -> dict | None:
        calls["parse"] += 1
        return parse_result

    service = ImageMetaService(engine=engine, fetch_fn=fake_fetch, parse_fn=fake_parse)
    return service, engine, calls


def test_first_call_fetches_and_caches_when_parse_succeeds():
    service, engine, calls = _make_service(
        fetch_returns=b"RIFF...",
        parse_result={"prompt": "test", "source": "exif_user_comment"},
    )
    result = service.get_or_fetch(article_id=42, url=URL)
    assert result == {"has_nai": True, "cached": False}
    assert calls["fetch"] == 1 and calls["parse"] == 1

    with Session(engine) as s:
        rows = s.exec(select(ImageMetaCache)).all()
    assert len(rows) == 1
    assert rows[0].article_id == 42
    assert rows[0].has_nai is True
    assert rows[0].payload_json is not None
    assert _j.loads(rows[0].payload_json) == {"prompt": "test", "source": "exif_user_comment"}


def test_second_call_returns_cached_without_fetch():
    service, _, calls = _make_service(parse_result={"prompt": "cached"})
    service.get_or_fetch(article_id=42, url=URL)
    result = service.get_or_fetch(article_id=42, url=URL)
    assert result == {"has_nai": True, "cached": True}
    assert calls["fetch"] == 1


def test_different_article_id_does_not_share_cache():
    service, _, calls = _make_service(parse_result={"prompt": "diff"})
    service.get_or_fetch(article_id=1, url=URL)
    service.get_or_fetch(article_id=2, url=URL)
    assert calls["fetch"] == 2


def test_fetch_returning_none_does_not_cache():
    service, engine, calls = _make_service(fetch_returns=None)
    result = service.get_or_fetch(article_id=42, url=URL)
    assert result == {"has_nai": False, "cached": False}
    with Session(engine) as s:
        rows = s.exec(select(ImageMetaCache)).all()
    assert len(rows) == 0


def test_non_nai_result_is_cached():
    service, _, calls = _make_service(parse_result=None)
    first = service.get_or_fetch(article_id=42, url=URL)
    assert first == {"has_nai": False, "cached": False}
    second = service.get_or_fetch(article_id=42, url=URL)
    assert second == {"has_nai": False, "cached": True}
    assert calls["fetch"] == 1


def test_url_without_hex_uses_sha1_fallback():
    service, engine, _ = _make_service(parse_result={"prompt": "sha1"})
    service.get_or_fetch(article_id=42, url="https://ac-p3.namu.la/file.png")
    with Session(engine) as s:
        row = s.exec(select(ImageMetaCache)).first()
    assert row is not None
    prefix, digest = row.key.split("_", 1)
    assert prefix == "42"
    assert len(digest) == 40
    assert all(c in "0123456789abcdef" for c in digest)


def test_include_full_returns_metadata_on_miss():
    service, _, _ = _make_service(parse_result={"prompt": "x", "steps": 28})
    result = service.get_or_fetch(article_id=42, url=URL, include_full=True)
    assert result == {"has_nai": True, "cached": False, "metadata": {"prompt": "x", "steps": 28}}


def test_include_full_returns_metadata_on_hit():
    service, _, calls = _make_service(parse_result={"prompt": "y"})
    service.get_or_fetch(article_id=42, url=URL, include_full=True)
    result = service.get_or_fetch(article_id=42, url=URL, include_full=True)
    assert result == {"has_nai": True, "cached": True, "metadata": {"prompt": "y"}}
    assert calls["fetch"] == 1


def test_include_full_with_legacy_row_forces_remiss_and_backfill():
    """Legacy cache row (has_nai=true, payload_json=NULL) is treated as miss when include_full=True."""
    service, engine, calls = _make_service(parse_result={"prompt": "fresh"})
    with Session(engine) as s:
        s.add(ImageMetaCache(
            key=_make_key(42, URL),
            article_id=42,
            has_nai=True,
            payload_json=None,
            fetched_at=datetime.now(timezone.utc),
        ))
        s.commit()

    result = service.get_or_fetch(article_id=42, url=URL, include_full=True)
    assert result["has_nai"] is True
    assert result["cached"] is False  # forced miss
    assert result["metadata"] == {"prompt": "fresh"}
    assert calls["fetch"] == 1

    with Session(engine) as s:
        rows = s.exec(select(ImageMetaCache)).all()
    assert len(rows) == 1
    assert rows[0].payload_json is not None
