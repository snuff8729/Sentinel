import asyncio
from unittest.mock import MagicMock

from sqlmodel import Session

from app.backup.events import Event, EventBus
from app.backup.service import BackupService
from app.backup.worker import BackupWorker
from app.db.engine import create_engine_and_tables
from app.db.repository import get_article


SAMPLE_HTML = '''
<html>
<div class="article-head">
    <span class="title">일반통합테스트</span>
    <span class="badge">일반</span>
    <div class="user-info">작성자</div>
    <div class="article-info">
        <span class="head">추천</span><span class="body">0</span>
        <span class="head">비추천</span><span class="body">0</span>
        <span class="head">댓글</span><span class="body">0</span>
        <span class="head">조회수</span><span class="body">10</span>
        <span class="head">작성일</span><span class="body"><time datetime="2026-04-18T08:00:00.000Z">2026-04-18</time></span>
    </div>
</div>
<div class="article-body">
    <div class="article-content">
        <img src="//ac-p3.namu.la/img1.png?expires=1&key=x" width="100">
        <img src="//ac-p3.namu.la/img2.png?expires=1&key=x" width="100">
    </div>
</div>
</html>
'''


def test_worker_processes_multiple_articles(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_HTML
    mock_resp.content = b"fake"
    mock_client.get.return_value = mock_resp

    event_bus = EventBus()
    service = BackupService(engine=engine, client=mock_client, data_dir=str(data_dir))
    worker = BackupWorker(service=service, event_bus=event_bus)

    events = []

    async def run():
        q = event_bus.subscribe()
        task = asyncio.create_task(worker.run())
        await worker.enqueue(1, "ch")
        await worker.enqueue(2, "ch")
        await worker._queue.join()
        await asyncio.sleep(0.1)
        while not q.empty():
            events.append(await q.get())
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())

    with Session(engine) as session:
        a1 = get_article(session, 1)
        a2 = get_article(session, 2)
        assert a1.backup_status == "completed"
        assert a2.backup_status == "completed"

    types = [e.type for e in events]
    assert types.count("article_started") == 2
    assert types.count("article_completed") == 2
    engine.dispose()


def test_worker_recovers_in_progress_on_startup(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")

    from app.db.repository import create_article, update_article_status
    from datetime import datetime, timezone
    with Session(engine) as session:
        create_article(
            session, id=999, channel_slug="t", title="stuck", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            url="https://arca.live/b/t/999",
        )
        update_article_status(session, 999, "in_progress")

    mock_client = MagicMock()
    event_bus = EventBus()
    service = BackupService(engine=engine, client=mock_client, data_dir=str(tmp_path / "data"))
    worker = BackupWorker(service=service, event_bus=event_bus)

    async def run():
        task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())

    with Session(engine) as session:
        art = get_article(session, 999)
        assert art.backup_status == "pending"
    engine.dispose()
