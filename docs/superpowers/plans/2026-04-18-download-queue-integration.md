# 다운로드 큐 연동 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 다운로드 큐를 BackupService에 연동하고, BackupWorker로 백그라운드 처리 + SSE 실시간 이벤트 + REST API 제어를 구현한다.

**Architecture:** EventBus(pub-sub)가 워커와 SSE를 연결하고, BackupWorker가 게시글 큐를 순차 처리하며, DownloadQueue가 도메인별 딜레이/동시실행을 적용한다. 일시정지는 asyncio.Event, 취소는 플래그 체크로 구현.

**Tech Stack:** Python 3.14, FastAPI, asyncio, SSE (StreamingResponse), SQLModel

**Spec:** `docs/superpowers/specs/2026-04-18-download-queue-integration-design.md`

---

### Task 1: EventBus — SSE 이벤트 발행/구독

**Files:**
- Create: `app/backup/events.py`
- Create: `tests/backup/test_events.py`

- [ ] **Step 1: 테스트 작성**

`tests/backup/test_events.py`:

```python
import asyncio

from app.backup.events import Event, EventBus


def test_publish_and_subscribe():
    bus = EventBus()

    received = []

    async def run():
        q = bus.subscribe()
        bus.publish(Event(type="test", data={"key": "value"}))
        event = await asyncio.wait_for(q.get(), timeout=1.0)
        received.append(event)

    asyncio.run(run())
    assert len(received) == 1
    assert received[0].type == "test"
    assert received[0].data == {"key": "value"}


def test_multiple_subscribers():
    bus = EventBus()

    async def run():
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        bus.publish(Event(type="hello", data={}))
        e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert e1.type == "hello"
        assert e2.type == "hello"

    asyncio.run(run())


def test_unsubscribe():
    bus = EventBus()

    async def run():
        q = bus.subscribe()
        bus.unsubscribe(q)
        bus.publish(Event(type="ignored", data={}))
        assert q.empty()

    asyncio.run(run())


def test_publish_no_subscribers():
    bus = EventBus()
    # Should not raise
    bus.publish(Event(type="orphan", data={}))
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/backup/test_events.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: events.py 구현**

`app/backup/events.py`:

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class Event:
    type: str
    data: dict = field(default_factory=dict)


class EventBus:
    def __init__(self):
        self._subscribers: list[asyncio.Queue[Event]] = []

    def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        self._subscribers = [s for s in self._subscribers if s is not q]

    def publish(self, event: Event) -> None:
        for q in self._subscribers:
            q.put_nowait(event)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/backup/test_events.py -v
```

Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add app/backup/events.py tests/backup/test_events.py
git commit -m "feat: add EventBus for SSE event pub-sub"
```

---

### Task 2: DownloadQueue — pause/cancel 지원 추가

**Files:**
- Modify: `app/backup/queue.py`
- Modify: `tests/backup/test_queue.py`

- [ ] **Step 1: 기존 테스트에 pause/cancel 테스트 추가**

`tests/backup/test_queue.py`에 아래 테스트 추가:

```python
def test_download_pauses_and_resumes():
    pause_event = asyncio.Event()
    pause_event.set()  # start running

    q = DownloadQueue(
        domain_overrides={"ac-p3.namu.la": DomainConfig(concurrency=1, delay=0.0)}
    )
    order = []

    async def tracked_download(url: str, dest: str):
        order.append(url)

    async def run():
        # Submit 3 items
        await q.submit(
            "https://ac-p3.namu.la/1.png", "/tmp/1.png", tracked_download,
            pause_event=pause_event,
        )
        # Pause after first submit
        pause_event.clear()
        await q.submit(
            "https://ac-p3.namu.la/2.png", "/tmp/2.png", tracked_download,
            pause_event=pause_event,
        )
        # Let first complete, second should be blocked
        await asyncio.sleep(0.2)
        assert len(order) == 1  # only first completed

        # Resume
        pause_event.set()
        await q.wait_all()
        assert len(order) == 2

    asyncio.run(run())


def test_download_cancels():
    q = DownloadQueue(
        domain_overrides={"ac-p3.namu.la": DomainConfig(concurrency=1, delay=0.0)}
    )
    order = []
    cancelled = False

    async def tracked_download(url: str, dest: str):
        order.append(url)

    async def run():
        nonlocal cancelled
        cancel_check = lambda: cancelled

        await q.submit(
            "https://ac-p3.namu.la/1.png", "/tmp/1.png", tracked_download,
            cancel_check=cancel_check,
        )
        cancelled = True
        await q.submit(
            "https://ac-p3.namu.la/2.png", "/tmp/2.png", tracked_download,
            cancel_check=cancel_check,
        )
        await q.wait_all()
        assert len(order) == 1  # second was cancelled

    asyncio.run(run())
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/backup/test_queue.py::test_download_pauses_and_resumes -v
uv run pytest tests/backup/test_queue.py::test_download_cancels -v
```

Expected: FAIL — `TypeError: submit() got an unexpected keyword argument 'pause_event'`

- [ ] **Step 3: queue.py 수정 — submit에 pause_event/cancel_check 추가**

`app/backup/queue.py`의 `submit` 메서드를 수정:

```python
    async def submit(
        self,
        url: str,
        dest: str,
        download_fn: Callable[[str, str], Awaitable[None]],
        *,
        pause_event: asyncio.Event | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        domain = urlparse(url).netloc
        domain_key = self._domain_key(domain)
        config = self.get_domain_config(domain)
        sem = self._get_semaphore(domain_key, config.concurrency)

        async def _run():
            async with sem:
                # Cancel check before waiting
                if cancel_check and cancel_check():
                    return

                # Pause check
                if pause_event is not None:
                    await pause_event.wait()

                # Delay enforcement
                async with self._lock:
                    last = self._last_request[domain_key]
                    now = time.monotonic()
                    wait = config.delay - (now - last)
                    if wait > 0:
                        self._last_request[domain_key] = now + wait
                    else:
                        self._last_request[domain_key] = now
                if wait > 0:
                    await asyncio.sleep(wait)

                # Cancel check after waiting
                if cancel_check and cancel_check():
                    return

                await download_fn(url, dest)

        task = asyncio.create_task(_run())
        self._tasks.append(task)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/backup/test_queue.py -v
```

Expected: 9 passed (기존 7 + 새 2)

- [ ] **Step 5: 커밋**

```bash
git add app/backup/queue.py tests/backup/test_queue.py
git commit -m "feat: add pause/cancel support to DownloadQueue"
```

---

### Task 3: BackupService — DownloadQueue 연동 + pause/cancel

**Files:**
- Modify: `app/backup/service.py`
- Modify: `tests/backup/test_service.py`

- [ ] **Step 1: 테스트 수정 — pause_event/cancel_check/event_bus 파라미터 추가**

`tests/backup/test_service.py`를 전체 교체:

```python
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
    cancelled = True  # cancel immediately

    asyncio.run(service.backup_article(
        article_id=100, channel_slug="test",
        event_bus=event_bus,
        cancel_check=lambda: cancelled,
    ))
    with Session(engine) as session:
        art = get_article(session, 100)
        assert art.backup_status == "cancelled"
    engine.dispose()
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/backup/test_service.py -v
```

Expected: FAIL — `TypeError: backup_article() got an unexpected keyword argument 'event_bus'`

- [ ] **Step 3: service.py 전체 재작성**

`app/backup/service.py`:

```python
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

from app.backup.events import Event, EventBus
from app.backup.media import MediaItem, extract_media_from_html, replace_urls_in_html
from app.backup.queue import DownloadQueue
from app.db.engine import get_session
from app.db.repository import (
    create_article,
    create_download,
    get_article,
    get_downloads_for_article,
    is_article_completed,
    update_article_status,
    update_download_status,
)
from app.scraper.arca.parser import parse_article_detail


class BackupService:
    def __init__(self, engine, client, data_dir: str = "data"):
        self._engine = engine
        self._client = client
        self._data_dir = Path(data_dir)
        self._queue = DownloadQueue()

    async def backup_article(
        self,
        article_id: int,
        channel_slug: str,
        *,
        force: bool = False,
        pause_event: asyncio.Event | None = None,
        cancel_check: Callable[[], bool] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        def _emit(event_type: str, data: dict | None = None):
            if event_bus:
                event_bus.publish(Event(type=event_type, data=data or {}))

        with get_session(self._engine) as session:
            if not force and is_article_completed(session, article_id):
                return

            # 1. Fetch detail page
            logger.info("[%d] 상세 페이지 가져오는 중...", article_id)
            resp = await asyncio.to_thread(
                self._client.get, f"/b/{channel_slug}/{article_id}"
            )
            html = resp.text

            # 2. Parse meta + create/update Article record
            detail = parse_article_detail(html, article_id)
            logger.info("[%d] '%s' by %s", article_id, detail.title, detail.author)
            article = get_article(session, article_id)
            if article is None:
                article = create_article(
                    session,
                    id=article_id,
                    channel_slug=channel_slug,
                    title=detail.title,
                    author=detail.author,
                    category=detail.category,
                    created_at=detail.created_at,
                    url=f"https://arca.live/b/{channel_slug}/{article_id}",
                )
            update_article_status(session, article_id, "in_progress")

        # 3. Extract media
        media_items = extract_media_from_html(html, article_id)
        emoticons = [m for m in media_items if m.file_type == "emoticon"]
        media = [m for m in media_items if m.file_type != "emoticon"]
        total_files = len(media_items)
        logger.info(
            "[%d] 미디어 %d개 발견 (일반 %d + 아카콘 %d)",
            article_id, total_files, len(media), len(emoticons),
        )

        _emit("article_started", {
            "article_id": article_id,
            "title": detail.title,
            "total_files": total_files,
        })

        # Cancel check after page fetch
        if cancel_check and cancel_check():
            with get_session(self._engine) as session:
                update_article_status(session, article_id, "cancelled")
            return

        # 4. Create Download records
        with get_session(self._engine) as session:
            if force:
                for dl in get_downloads_for_article(session, article_id):
                    update_download_status(session, dl.id, "pending")

            existing_urls = {d.url for d in get_downloads_for_article(session, article_id)}
            for item in media_items:
                if item.url not in existing_urls:
                    create_download(
                        session,
                        article_id=article_id,
                        url=item.url,
                        local_path=item.local_path,
                        file_type=item.file_type,
                    )
                    existing_urls.add(item.url)

        # 5a. 아카콘 — 병렬, 큐 안 탐
        emoticon_results = await self._download_emoticons(article_id, emoticons, _emit)

        # 5b. 일반 미디어 — 큐 통해 다운로드
        media_results = await self._download_media(
            article_id, media, _emit,
            pause_event=pause_event,
            cancel_check=cancel_check,
        )

        completed_count = emoticon_results["completed"] + media_results["completed"]
        failed_count = emoticon_results["failed"] + media_results["failed"]
        skipped_count = emoticon_results["skipped"]
        cancelled = media_results.get("cancelled", False)

        logger.info(
            "[%d] 다운로드 완료: %d 성공, %d 스킵(아카콘), %d 실패%s",
            article_id, completed_count, skipped_count, failed_count,
            " (취소됨)" if cancelled else "",
        )

        # 6. Replace URLs + save backup HTML (취소되어도 부분 백업 보존)
        url_to_relative = {m.url: m.relative_path for m in media_items}
        backup_html = replace_urls_in_html(html, url_to_relative)
        backup_path = self._data_dir / "articles" / str(article_id) / "backup.html"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(backup_html, encoding="utf-8")

        # 7. Final status
        with get_session(self._engine) as session:
            if cancelled:
                update_article_status(session, article_id, "cancelled")
            elif failed_count > 0:
                update_article_status(
                    session, article_id, "failed",
                    error=f"{failed_count} file(s) failed to download",
                )
            else:
                update_article_status(session, article_id, "completed")

        _emit("article_completed", {
            "article_id": article_id,
            "success_count": completed_count,
            "fail_count": failed_count,
        })

    async def _download_emoticons(
        self, article_id: int, emoticons: list[MediaItem], emit,
    ) -> dict[str, int]:
        results = {"completed": 0, "failed": 0, "skipped": 0}
        if not emoticons:
            return results

        async def _download_one(item: MediaItem):
            dest = self._data_dir / item.local_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            if dest.exists():
                results["skipped"] += 1
                logger.info("[%d] 아카콘 스킵: %s (이미 존재)", article_id, dest.name)
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "completed")
                            break
                return

            try:
                file_resp = await asyncio.to_thread(self._client.get, item.url)
                dest.write_bytes(file_resp.content)
                results["completed"] += 1
                logger.info(
                    "[%d] 아카콘 다운: %s %.1fKB",
                    article_id, dest.name, len(file_resp.content) / 1024,
                )
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "completed")
                            break
                emit("file_completed", {
                    "article_id": article_id,
                    "filename": dest.name,
                    "size_kb": round(len(file_resp.content) / 1024, 1),
                    "file_type": "emoticon",
                })
            except Exception as e:
                results["failed"] += 1
                logger.warning("[%d] 아카콘 실패: %s — %s", article_id, dest.name, e)
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "failed", error=str(e))
                            break
                emit("file_failed", {
                    "article_id": article_id,
                    "filename": dest.name,
                    "error": str(e),
                })

        await asyncio.gather(*[_download_one(item) for item in emoticons])
        return results

    async def _download_media(
        self,
        article_id: int,
        media: list[MediaItem],
        emit,
        *,
        pause_event: asyncio.Event | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict:
        results = {"completed": 0, "failed": 0, "cancelled": False}
        total = len(media)
        if not total:
            return results

        completed_so_far = 0

        async def _do_download(url: str, dest_str: str):
            nonlocal completed_so_far
            dest = Path(dest_str)
            item = next(m for m in media if m.url == url)
            try:
                file_resp = await asyncio.to_thread(self._client.get, url)
                dest.write_bytes(file_resp.content)
                results["completed"] += 1
                completed_so_far += 1
                size_kb = len(file_resp.content) / 1024
                logger.info(
                    "[%d] [%d/%d] ✓ %s %.1fKB (%s)",
                    article_id, completed_so_far, total, dest.name, size_kb, item.file_type,
                )
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == url:
                            update_download_status(session, dl.id, "completed")
                            break
                emit("file_completed", {
                    "article_id": article_id,
                    "filename": dest.name,
                    "size_kb": round(size_kb, 1),
                    "current": completed_so_far,
                    "total": total,
                    "file_type": item.file_type,
                })
            except Exception as e:
                results["failed"] += 1
                completed_so_far += 1
                logger.warning(
                    "[%d] [%d/%d] ✗ %s 실패: %s",
                    article_id, completed_so_far, total, dest.name, e,
                )
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == url:
                            update_download_status(session, dl.id, "failed", error=str(e))
                            break
                emit("file_failed", {
                    "article_id": article_id,
                    "filename": dest.name,
                    "error": str(e),
                })

        for item in media:
            if cancel_check and cancel_check():
                results["cancelled"] = True
                break

            dest = self._data_dir / item.local_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            await self._queue.submit(
                url=item.url,
                dest=str(dest),
                download_fn=_do_download,
                pause_event=pause_event,
                cancel_check=cancel_check,
            )

        await self._queue.wait_all()
        return results
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/backup/test_service.py -v
```

Expected: 7 passed

- [ ] **Step 5: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 통과

- [ ] **Step 6: 커밋**

```bash
git add app/backup/service.py tests/backup/test_service.py
git commit -m "feat: integrate DownloadQueue + pause/cancel/events into BackupService"
```

---

### Task 4: BackupWorker — 게시글 큐 + 일시정지/취소 제어

**Files:**
- Create: `app/backup/worker.py`
- Create: `tests/backup/test_worker.py`

- [ ] **Step 1: 테스트 작성**

`tests/backup/test_worker.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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
        # Should have processed 1, but 2 is blocked
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
        # Cancel article 2 while 1 is processing
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
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/backup/test_worker.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: worker.py 구현**

`app/backup/worker.py`:

```python
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.backup.events import Event, EventBus
from app.backup.service import BackupService

logger = logging.getLogger(__name__)


@dataclass
class BackupRequest:
    article_id: int
    channel_slug: str


class BackupWorker:
    def __init__(self, service: BackupService, event_bus: EventBus):
        self._service = service
        self._event_bus = event_bus
        self._queue: asyncio.Queue[BackupRequest] = asyncio.Queue()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # start running
        self._cancelled: set[int] = set()
        self._current: BackupRequest | None = None
        self._pending: list[BackupRequest] = []

    async def enqueue(self, article_id: int, channel_slug: str) -> int:
        req = BackupRequest(article_id=article_id, channel_slug=channel_slug)
        self._pending.append(req)
        await self._queue.put(req)
        self._event_bus.publish(Event(type="queue_updated", data=self._queue_snapshot()))
        return len(self._pending)

    def pause(self) -> None:
        self._pause_event.clear()
        logger.info("Worker paused")
        self._event_bus.publish(Event(type="worker_paused"))

    def resume(self) -> None:
        self._pause_event.set()
        logger.info("Worker resumed")
        self._event_bus.publish(Event(type="worker_resumed"))

    def cancel(self, article_id: int) -> None:
        self._cancelled.add(article_id)
        self._pending = [r for r in self._pending if r.article_id != article_id]
        logger.info("Cancelled article %d", article_id)
        self._event_bus.publish(Event(type="queue_updated", data=self._queue_snapshot()))

    def get_status(self) -> dict:
        current = None
        if self._current:
            current = {
                "article_id": self._current.article_id,
                "channel_slug": self._current.channel_slug,
            }
        return {
            "paused": not self._pause_event.is_set(),
            "current": current,
            "pending": [
                {"article_id": r.article_id, "channel_slug": r.channel_slug}
                for r in self._pending
            ],
        }

    async def run(self) -> None:
        logger.info("BackupWorker started")
        while True:
            req = await self._queue.get()

            # Remove from pending
            self._pending = [r for r in self._pending if r.article_id != req.article_id]

            # Skip if cancelled
            if req.article_id in self._cancelled:
                self._cancelled.discard(req.article_id)
                self._queue.task_done()
                continue

            # Wait if paused
            await self._pause_event.wait()

            self._current = req
            logger.info("Processing article %d", req.article_id)

            try:
                await self._service.backup_article(
                    article_id=req.article_id,
                    channel_slug=req.channel_slug,
                    pause_event=self._pause_event,
                    cancel_check=lambda aid=req.article_id: aid in self._cancelled,
                    event_bus=self._event_bus,
                )
            except Exception as e:
                logger.error("Failed to backup article %d: %s", req.article_id, e)

            self._current = None
            self._queue.task_done()

    def _queue_snapshot(self) -> dict:
        return {
            "queue": [
                {"article_id": r.article_id, "channel_slug": r.channel_slug}
                for r in self._pending
            ],
        }
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/backup/test_worker.py -v
```

Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add app/backup/worker.py tests/backup/test_worker.py
git commit -m "feat: add BackupWorker with queue, pause, cancel, status"
```

---

### Task 5: API 엔드포인트 — REST + SSE

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/backup.py`
- Modify: `app/main.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/test_backup.py`

- [ ] **Step 1: sse 의존성 추가**

```bash
uv add sse-starlette
```

- [ ] **Step 2: 디렉토리 생성**

```bash
mkdir -p app/api tests/api
touch app/api/__init__.py tests/api/__init__.py
```

- [ ] **Step 3: httpx test 의존성 추가**

```bash
uv add --dev httpx
```

- [ ] **Step 4: 테스트 작성**

`tests/api/test_backup.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.backup import create_backup_router
from app.backup.events import EventBus
from app.backup.worker import BackupWorker
from app.main import app


def _setup():
    service = MagicMock()
    service.backup_article = AsyncMock()
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)
    router = create_backup_router(worker, event_bus)
    app.include_router(router, prefix="/api/backup")
    return app, worker, event_bus


@pytest.fixture
def client():
    test_app, worker, event_bus = _setup()
    # Start worker in background
    return TestClient(test_app)


def test_enqueue_backup(client):
    resp = client.post("/api/backup/test/100")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"


def test_get_queue_status(client):
    resp = client.get("/api/backup/queue")
    assert resp.status_code == 200
    data = resp.json()
    assert "paused" in data
    assert "pending" in data


def test_pause(client):
    resp = client.post("/api/backup/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


def test_resume(client):
    client.post("/api/backup/pause")
    resp = client.post("/api/backup/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resumed"


def test_cancel(client):
    client.post("/api/backup/test/100")
    resp = client.delete("/api/backup/100")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
```

- [ ] **Step 5: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/api/test_backup.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 6: api/backup.py 구현**

`app/api/backup.py`:

```python
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from app.backup.events import EventBus
from app.backup.worker import BackupWorker


def create_backup_router(worker: BackupWorker, event_bus: EventBus) -> APIRouter:
    router = APIRouter()

    @router.post("/{channel_slug}/{article_id}")
    async def enqueue_backup(channel_slug: str, article_id: int):
        position = await worker.enqueue(article_id, channel_slug)
        return {"status": "queued", "position": position}

    @router.delete("/{article_id}")
    async def cancel_backup(article_id: int):
        worker.cancel(article_id)
        return {"status": "cancelled"}

    @router.post("/pause")
    async def pause_worker():
        worker.pause()
        return {"status": "paused"}

    @router.post("/resume")
    async def resume_worker():
        worker.resume()
        return {"status": "resumed"}

    @router.get("/queue")
    async def get_queue():
        return worker.get_status()

    @router.get("/events")
    async def backup_events():
        q = event_bus.subscribe()

        async def generate():
            try:
                while True:
                    event = await q.get()
                    yield f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                event_bus.unsubscribe(q)

        return StreamingResponse(generate(), media_type="text/event-stream")

    return router
```

- [ ] **Step 7: main.py 수정**

`app/main.py`:

```python
import asyncio

from fastapi import FastAPI

from app.api.backup import create_backup_router
from app.backup.events import EventBus
from app.backup.service import BackupService
from app.backup.worker import BackupWorker
from app.db.engine import create_engine_and_tables
from app.scraper.arca.client import ArcaClient

app = FastAPI(title="Sentinel")

worker: BackupWorker | None = None


@app.on_event("startup")
async def startup():
    global worker
    engine = create_engine_and_tables()
    client = ArcaClient()
    event_bus = EventBus()
    service = BackupService(engine=engine, client=client)
    worker = BackupWorker(service=service, event_bus=event_bus)

    router = create_backup_router(worker, event_bus)
    app.include_router(router, prefix="/api/backup")

    asyncio.create_task(worker.run())


@app.get("/")
async def root():
    return {"message": "Hello from Sentinel"}


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 8: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/api/test_backup.py -v
```

Expected: 5 passed

- [ ] **Step 9: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 통과

- [ ] **Step 10: 커밋**

```bash
git add app/api/ app/main.py tests/api/
git commit -m "feat: add REST + SSE API endpoints for backup control"
```

---

### Task 6: 통합 테스트 + startup 복구 로직

**Files:**
- Modify: `app/backup/worker.py`
- Create: `tests/backup/test_integration.py`

- [ ] **Step 1: startup 복구 로직 — in_progress를 pending으로 되돌리기**

`app/backup/worker.py`의 `run()` 메서드 시작 부분에 추가:

```python
    async def run(self) -> None:
        # Startup recovery: reset in_progress articles to pending
        from app.db.engine import get_session
        from app.db.models import Article
        from sqlmodel import select

        engine = self._service._engine
        with get_session(engine) as session:
            stmt = select(Article).where(Article.backup_status == "in_progress")
            stuck = session.exec(stmt).all()
            for art in stuck:
                art.backup_status = "pending"
                session.add(art)
            if stuck:
                session.commit()
                logger.info("Recovered %d stuck articles to pending", len(stuck))

        logger.info("BackupWorker started")
        while True:
            # ... rest unchanged
```

- [ ] **Step 2: 통합 테스트 작성**

`tests/backup/test_integration.py`:

```python
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
        await asyncio.sleep(1.0)
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

    # Manually create a stuck article
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
```

- [ ] **Step 3: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/backup/test_integration.py -v
```

Expected: 2 passed

- [ ] **Step 4: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 통과

- [ ] **Step 5: 커밋**

```bash
git add app/backup/worker.py tests/backup/test_integration.py
git commit -m "feat: add startup recovery + integration tests for worker pipeline"
```
