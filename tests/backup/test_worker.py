import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.backup.events import EventBus
from app.backup.worker import BackupWorker


def _mock_service():
    service = MagicMock()
    service.backup_article = AsyncMock()
    return service


def test_enqueue_and_process():
    service = _mock_service()
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)

    async def run():
        task = asyncio.create_task(worker.run())
        await worker.enqueue(100, "test")
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
    service.backup_article.assert_called_once()
    call_kwargs = service.backup_article.call_args
    assert call_kwargs.kwargs["article_id"] == 100
    assert call_kwargs.kwargs["channel_slug"] == "test"


def test_enqueue_multiple_sequential():
    service = _mock_service()
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)
    call_order = []

    async def track_call(**kwargs):
        call_order.append(kwargs["article_id"])
        await asyncio.sleep(0.05)

    service.backup_article = AsyncMock(side_effect=track_call)

    async def run():
        task = asyncio.create_task(worker.run())
        await worker.enqueue(1, "ch")
        await worker.enqueue(2, "ch")
        await worker.enqueue(3, "ch")
        await asyncio.sleep(0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
    assert call_order == [1, 2, 3]


def test_pause_and_resume():
    service = _mock_service()
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)
    events_received = []

    async def slow_backup(**kwargs):
        await asyncio.sleep(0.1)

    service.backup_article = AsyncMock(side_effect=slow_backup)

    async def run():
        q = event_bus.subscribe()
        task = asyncio.create_task(worker.run())

        await worker.enqueue(1, "ch")
        await worker.enqueue(2, "ch")
        await asyncio.sleep(0.05)
        worker.pause()
        await asyncio.sleep(0.3)
        assert service.backup_article.call_count <= 2

        worker.resume()
        await asyncio.sleep(0.3)

        while not q.empty():
            events_received.append(await q.get())

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
    types = [e.type for e in events_received]
    assert "worker_paused" in types
    assert "worker_resumed" in types


def test_cancel_removes_from_queue():
    service = _mock_service()
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)

    async def slow_backup(**kwargs):
        await asyncio.sleep(0.2)

    service.backup_article = AsyncMock(side_effect=slow_backup)

    async def run():
        task = asyncio.create_task(worker.run())
        await worker.enqueue(1, "ch")
        await worker.enqueue(2, "ch")
        await worker.enqueue(3, "ch")
        await asyncio.sleep(0.05)
        worker.cancel(2)
        await asyncio.sleep(0.6)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
    called_ids = [c.kwargs["article_id"] for c in service.backup_article.call_args_list]
    assert 2 not in called_ids
    assert 1 in called_ids
    assert 3 in called_ids


def test_get_status():
    service = _mock_service()
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)

    async def slow_backup(**kwargs):
        await asyncio.sleep(0.3)

    service.backup_article = AsyncMock(side_effect=slow_backup)

    async def run():
        task = asyncio.create_task(worker.run())
        await worker.enqueue(1, "ch")
        await worker.enqueue(2, "ch")
        await asyncio.sleep(0.05)
        status = worker.get_status()
        assert status["paused"] is False
        assert status["current"]["article_id"] == 1
        assert len(status["pending"]) == 1
        assert status["pending"][0]["article_id"] == 2
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
