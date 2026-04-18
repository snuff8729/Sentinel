import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from sqlmodel import Session

from app.backup.events import EventBus
from app.backup.service import BackupService
from app.db.engine import create_engine_and_tables
from app.db.repository import get_article, get_downloads_for_article


SAMPLE_HTML = '''
<html>
<div class="article-head">
    <span class="title">일반테스트 게시글</span>
    <span class="badge">일반</span>
    <div class="user-info">작성자</div>
    <div class="article-info">
        <span class="head">추천</span><span class="body">5</span>
        <span class="head">비추천</span><span class="body">0</span>
        <span class="head">댓글</span><span class="body">2</span>
        <span class="head">조회수</span><span class="body">100</span>
        <span class="head">작성일</span><span class="body"><time datetime="2026-04-18T08:00:00.000Z">2026-04-18</time></span>
    </div>
</div>
<div class="article-body">
    <div class="article-content">
        <img src="//ac-p3.namu.la/20260418sac/abc123.png?expires=1&key=x" width="800">
        <img class="arca-emoticon" data-store-id="9999" src="//ac-p3.namu.la/emote.png?expires=1&key=x" width="100">
    </div>
</div>
</html>
'''


def _setup(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_HTML
    mock_resp.content = b"fake image bytes"
    mock_client.get.return_value = mock_resp

    event_bus = EventBus()
    service = BackupService(engine=engine, client=mock_client, data_dir=str(data_dir))
    return engine, service, data_dir, event_bus


def test_backup_creates_article_record(tmp_path):
    engine, service, data_dir, event_bus = _setup(tmp_path)
    asyncio.run(service.backup_article(article_id=100, channel_slug="test", event_bus=event_bus))
    with Session(engine) as session:
        art = get_article(session, 100)
        assert art is not None
        assert art.title == "테스트 게시글"
        assert art.backup_status == "completed"
    engine.dispose()


def test_backup_downloads_media(tmp_path):
    engine, service, data_dir, event_bus = _setup(tmp_path)
    asyncio.run(service.backup_article(article_id=100, channel_slug="test", event_bus=event_bus))
    with Session(engine) as session:
        downloads = get_downloads_for_article(session, 100)
        assert len(downloads) == 2
        statuses = {d.status for d in downloads}
        assert statuses == {"completed"}
    engine.dispose()


def test_backup_creates_html_file(tmp_path):
    engine, service, data_dir, event_bus = _setup(tmp_path)
    asyncio.run(service.backup_article(article_id=100, channel_slug="test", event_bus=event_bus))
    backup_html = data_dir / "articles" / "100" / "backup.html"
    assert backup_html.exists()
    content = backup_html.read_text()
    assert "namu.la" not in content
    engine.dispose()


def test_backup_skips_completed(tmp_path):
    engine, service, data_dir, event_bus = _setup(tmp_path)
    asyncio.run(service.backup_article(article_id=100, channel_slug="test", event_bus=event_bus))
    call_count_before = service._client.get.call_count
    asyncio.run(service.backup_article(article_id=100, channel_slug="test", event_bus=event_bus))
    assert service._client.get.call_count == call_count_before
    engine.dispose()


def test_backup_force_redownload(tmp_path):
    engine, service, data_dir, event_bus = _setup(tmp_path)
    asyncio.run(service.backup_article(article_id=100, channel_slug="test", event_bus=event_bus))
    call_count_before = service._client.get.call_count
    asyncio.run(service.backup_article(article_id=100, channel_slug="test", force=True, event_bus=event_bus))
    assert service._client.get.call_count > call_count_before
    engine.dispose()


def test_backup_emits_events(tmp_path):
    engine, service, data_dir, event_bus = _setup(tmp_path)
    events = []
    async def run():
        q = event_bus.subscribe()
        await service.backup_article(article_id=100, channel_slug="test", event_bus=event_bus)
        while not q.empty():
            events.append(await q.get())
    asyncio.run(run())
    types = [e.type for e in events]
    assert "article_started" in types
    assert "file_completed" in types
    assert "article_completed" in types
    engine.dispose()


def test_backup_cancel_stops_processing(tmp_path):
    engine, service, data_dir, event_bus = _setup(tmp_path)
    cancelled = True
    asyncio.run(service.backup_article(
        article_id=100, channel_slug="test",
        event_bus=event_bus,
        cancel_check=lambda: cancelled,
    ))
    with Session(engine) as session:
        art = get_article(session, 100)
        assert art.backup_status == "cancelled"
    engine.dispose()
