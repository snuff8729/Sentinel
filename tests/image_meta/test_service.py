from sqlmodel import Session, select

from app.db.engine import create_engine_and_tables
from app.db.models import ImageMetaCache
from app.image_meta.service import ImageMetaService

URL = "https://ac-p3.namu.la/20260428sac/abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789.png?expires=1&key=x"


def _make_service(fetch_returns=b"RIFF\x00\x00\x00\x00WEBP", parse_result=False):
    engine = create_engine_and_tables("sqlite:///:memory:")
    calls = {"fetch": 0, "parse": 0}

    def fake_fetch(url: str) -> bytes | None:
        calls["fetch"] += 1
        return fetch_returns

    def fake_parse(buf: bytes) -> bool:
        calls["parse"] += 1
        return parse_result

    service = ImageMetaService(engine=engine, fetch_fn=fake_fetch, parse_fn=fake_parse)
    return service, engine, calls


def test_first_call_fetches_and_caches_when_parse_succeeds():
    service, engine, calls = _make_service(fetch_returns=b"RIFF...", parse_result=True)
    result = service.get_or_fetch(article_id=42, url=URL)
    assert result == {"has_nai": True, "cached": False}
    assert calls["fetch"] == 1 and calls["parse"] == 1

    with Session(engine) as s:
        rows = s.exec(select(ImageMetaCache)).all()
    assert len(rows) == 1
    assert rows[0].article_id == 42
    assert rows[0].has_nai is True


def test_second_call_returns_cached_without_fetch():
    service, _, calls = _make_service(parse_result=True)
    service.get_or_fetch(article_id=42, url=URL)
    result = service.get_or_fetch(article_id=42, url=URL)
    assert result == {"has_nai": True, "cached": True}
    assert calls["fetch"] == 1


def test_different_article_id_does_not_share_cache():
    service, _, calls = _make_service(parse_result=True)
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


def test_url_without_hex_uses_sha1_fallback():
    service, engine, _ = _make_service(parse_result=True)
    service.get_or_fetch(article_id=42, url="https://ac-p3.namu.la/file.png")
    with Session(engine) as s:
        row = s.exec(select(ImageMetaCache)).first()
    assert row is not None
    assert row.key.startswith("42_")
    assert len(row.key) == 3 + 40  # "42_" + sha1 hex (40 chars)
