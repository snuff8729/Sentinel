# 웹 UI 백엔드 API 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프론트엔드에서 사용할 채널/게시글 조회 API + 백업 이력 API를 추가하고, 빌드된 React 정적 파일을 FastAPI에서 서빙한다.

**Architecture:** `ArcaChannel` 스크래퍼를 REST API로 노출하는 `channel.py` 라우터를 추가하고, 기존 `backup.py`에 이력 조회를 추가한다. `main.py`에서 정적 파일 서빙 마운트를 설정한다.

**Tech Stack:** FastAPI, SQLModel, asyncio

**Spec:** `docs/superpowers/specs/2026-04-18-web-ui-design.md`

---

### Task 1: 채널/게시글 조회 API

**Files:**
- Create: `app/api/channel.py`
- Create: `tests/api/test_channel.py`

- [ ] **Step 1: 테스트 작성**

`tests/api/test_channel.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.channel import create_channel_router

FIXTURE_DIR = Path(__file__).parent.parent / "scraper" / "arca" / "fixtures"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def client():
    mock_arca_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = _load("article_list.html")
    mock_arca_client.get.return_value = mock_resp

    test_app = FastAPI()
    router = create_channel_router(mock_arca_client)
    test_app.include_router(router, prefix="/api/channel")
    return TestClient(test_app), mock_arca_client


def test_get_categories(client):
    test_client, _ = client
    resp = test_client.get("/api/channel/characterai/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert any(c["name"] == "전체" for c in data)


def test_get_articles(client):
    test_client, _ = client
    resp = test_client.get("/api/channel/characterai/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert "articles" in data
    assert "current_page" in data
    assert "total_pages" in data
    assert len(data["articles"]) > 0


def test_get_articles_with_params(client):
    test_client, mock_client = client
    resp = test_client.get("/api/channel/characterai/articles?category=일반&mode=best&page=2")
    assert resp.status_code == 200
    call_args = mock_client.get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("category") == "일반"
    assert params.get("mode") == "best"
    assert params.get("p") == 2


def test_search(client):
    test_client, mock_client = client
    resp = test_client.get("/api/channel/characterai/search?keyword=프롬&target=title")
    assert resp.status_code == 200
    data = resp.json()
    assert "articles" in data


def test_get_article_detail(client):
    test_client, mock_client = client
    detail_html = _load("article_detail.html")
    mock_resp = MagicMock()
    mock_resp.text = detail_html
    mock_client.get.return_value = mock_resp

    resp = test_client.get("/api/article/characterai/168046805")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 168046805
    assert "title" in data
    assert "content_html" in data


def test_get_comments(client):
    test_client, mock_client = client
    comments_html = _load("article_with_comments.html")
    mock_resp = MagicMock()
    mock_resp.text = comments_html
    mock_client.get.return_value = mock_resp

    resp = test_client.get("/api/article/characterai/168046700/comments")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert "id" in data[0]
    assert "author" in data[0]
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/api/test_channel.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: channel.py 구현**

`app/api/channel.py`:

```python
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.scraper.arca.channel import ArcaChannel


def create_channel_router(client) -> APIRouter:
    router = APIRouter()

    @router.get("/{slug}/categories")
    async def get_categories(slug: str):
        channel = ArcaChannel(client, slug)
        categories = await asyncio.to_thread(channel.get_categories)
        return [c.model_dump() for c in categories]

    @router.get("/{slug}/articles")
    async def get_articles(
        slug: str,
        category: str | None = None,
        mode: str | None = None,
        sort: str | None = None,
        cut: int | None = None,
        page: int = 1,
    ):
        channel = ArcaChannel(client, slug)
        result = await asyncio.to_thread(
            channel.get_articles,
            category=category,
            mode=mode,
            sort=sort,
            cut=cut,
            page=page,
        )
        return result.model_dump()

    @router.get("/{slug}/search")
    async def search_articles(
        slug: str,
        keyword: str,
        target: str = "all",
        page: int = 1,
    ):
        channel = ArcaChannel(client, slug)
        result = await asyncio.to_thread(
            channel.search,
            keyword,
            target=target,
            page=page,
        )
        return result.model_dump()

    # 게시글 상세 + 댓글은 /api/article/ 프리픽스로 별도 마운트
    article_router = APIRouter()

    @article_router.get("/{slug}/{article_id}")
    async def get_article(slug: str, article_id: int):
        channel = ArcaChannel(client, slug)
        detail = await asyncio.to_thread(channel.get_article, article_id)
        return detail.model_dump()

    @article_router.get("/{slug}/{article_id}/comments")
    async def get_comments(slug: str, article_id: int):
        channel = ArcaChannel(client, slug)
        comments = await asyncio.to_thread(channel.get_comments, article_id)
        return [c.model_dump() for c in comments]

    router.article_router = article_router  # attach for main.py to mount separately
    return router
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

테스트에서 article/comments 엔드포인트는 `/api/article/` 프리픽스를 사용하므로 테스트 fixture를 업데이트. 실제로는 `test_channel.py`에서 article_router도 마운트해야 합니다. 테스트 fixture를 수정:

`tests/api/test_channel.py`의 `client` fixture를 수정:

```python
@pytest.fixture
def client():
    mock_arca_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = _load("article_list.html")
    mock_arca_client.get.return_value = mock_resp

    test_app = FastAPI()
    router = create_channel_router(mock_arca_client)
    test_app.include_router(router, prefix="/api/channel")
    test_app.include_router(router.article_router, prefix="/api/article")
    return TestClient(test_app), mock_arca_client
```

```bash
uv run pytest tests/api/test_channel.py -v
```

Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add app/api/channel.py tests/api/test_channel.py
git commit -m "feat: add channel/article REST API endpoints"
```

---

### Task 2: 백업 이력 조회 API

**Files:**
- Modify: `app/db/repository.py`
- Modify: `app/api/backup.py`
- Create: `tests/api/test_backup_history.py`

- [ ] **Step 1: repository에 이력 조회 함수 추가 테스트**

`tests/db/test_repository.py`에 추가:

```python
def test_get_articles_by_status(tmp_path):
    with _session(tmp_path) as session:
        create_article(session, id=1, channel_slug="t", title="done1", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://arca.live/b/t/1")
        create_article(session, id=2, channel_slug="t", title="done2", author="a",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc), url="https://arca.live/b/t/2")
        create_article(session, id=3, channel_slug="t", title="fail", author="a",
            created_at=datetime(2026, 1, 3, tzinfo=timezone.utc), url="https://arca.live/b/t/3")
        update_article_status(session, 1, "completed")
        update_article_status(session, 2, "completed")
        update_article_status(session, 3, "failed", error="timeout")

        from app.db.repository import get_articles_by_status
        completed = get_articles_by_status(session, "completed")
        assert len(completed) == 2
        failed = get_articles_by_status(session, "failed")
        assert len(failed) == 1
        assert failed[0].backup_error == "timeout"
        all_arts = get_articles_by_status(session)
        assert len(all_arts) == 3
```

- [ ] **Step 2: repository.py에 함수 추가**

`app/db/repository.py`에 추가:

```python
def get_articles_by_status(session: Session, status: str | None = None) -> list[Article]:
    if status:
        statement = select(Article).where(Article.backup_status == status).order_by(Article.backed_up_at.desc())
    else:
        statement = select(Article).order_by(Article.id.desc())
    return list(session.exec(statement).all())
```

- [ ] **Step 3: repository 테스트 실행**

```bash
uv run pytest tests/db/test_repository.py -v
```

Expected: 8 passed

- [ ] **Step 4: API 테스트 작성**

`tests/api/test_backup_history.py`:

```python
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.api.backup import create_backup_router
from app.backup.events import EventBus
from app.backup.worker import BackupWorker
from app.db.engine import create_engine_and_tables
from app.db.repository import create_article, update_article_status
from sqlmodel import Session


@pytest.fixture
def setup(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")

    # Seed data
    with Session(engine) as session:
        create_article(session, id=1, channel_slug="ch", title="완료됨", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://arca.live/b/ch/1")
        create_article(session, id=2, channel_slug="ch", title="실패함", author="b",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc), url="https://arca.live/b/ch/2")
        update_article_status(session, 1, "completed")
        update_article_status(session, 2, "failed", error="HTTP 404")

    service = MagicMock()
    service._engine = engine
    service.backup_article = AsyncMock()
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)

    test_app = FastAPI()
    router = create_backup_router(worker, event_bus, engine)
    test_app.include_router(router, prefix="/api/backup")
    return TestClient(test_app), engine


def test_history_all(setup):
    client, engine = setup
    resp = client.get("/api/backup/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    engine.dispose()


def test_history_by_status(setup):
    client, engine = setup
    resp = client.get("/api/backup/history?status=completed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "완료됨"
    engine.dispose()


def test_history_failed(setup):
    client, engine = setup
    resp = client.get("/api/backup/history?status=failed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["backup_error"] == "HTTP 404"
    engine.dispose()
```

- [ ] **Step 5: backup.py 수정 — history 엔드포인트 + engine 파라미터 추가**

`app/api/backup.py`를 수정. `create_backup_router`에 `engine` 파라미터를 추가하고 `/history` 엔드포인트를 추가:

```python
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from app.backup.events import EventBus
from app.backup.worker import BackupWorker


def create_backup_router(worker: BackupWorker, event_bus: EventBus, engine=None) -> APIRouter:
    router = APIRouter()

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

    @router.get("/history")
    async def get_history(status: str | None = None):
        from app.db.engine import get_session
        from app.db.repository import get_articles_by_status
        _engine = engine or worker._service._engine
        with get_session(_engine) as session:
            articles = get_articles_by_status(session, status)
            return [
                {
                    "id": a.id,
                    "channel_slug": a.channel_slug,
                    "title": a.title,
                    "author": a.author,
                    "category": a.category,
                    "backup_status": a.backup_status,
                    "backup_error": a.backup_error,
                    "backed_up_at": a.backed_up_at.isoformat() if a.backed_up_at else None,
                }
                for a in articles
            ]

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

    @router.post("/{channel_slug}/{article_id}")
    async def enqueue_backup(channel_slug: str, article_id: int, force: bool = False):
        position = await worker.enqueue(article_id, channel_slug, force=force)
        return {"status": "queued", "position": position}

    @router.delete("/{article_id}")
    async def cancel_backup(article_id: int):
        worker.cancel(article_id)
        return {"status": "cancelled"}

    return router
```

- [ ] **Step 6: 기존 backup API 테스트 수정**

`tests/api/test_backup.py`의 fixture에서 `create_backup_router` 호출에 `engine=None`을 추가:

```python
router = create_backup_router(worker, event_bus, engine=None)
```

- [ ] **Step 7: main.py 수정 — engine을 backup router에 전달**

`app/main.py`에서 `create_backup_router` 호출 수정:

```python
router = create_backup_router(worker, event_bus, engine)
```

- [ ] **Step 8: 테스트 실행**

```bash
uv run pytest tests/api/ tests/db/test_repository.py -v
```

Expected: 모든 테스트 통과

- [ ] **Step 9: 커밋**

```bash
git add app/api/backup.py app/api/channel.py app/db/repository.py app/main.py tests/
git commit -m "feat: add backup history API + channel/article API endpoints"
```

---

### Task 3: main.py — 채널 라우터 등록 + 정적 파일 서빙

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: main.py 수정**

`app/main.py`:

```python
import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.backup import create_backup_router
from app.api.channel import create_channel_router
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

    # API routers
    channel_router = create_channel_router(client)
    app.include_router(channel_router, prefix="/api/channel")
    app.include_router(channel_router.article_router, prefix="/api/article")

    backup_router = create_backup_router(worker, event_bus, engine)
    app.include_router(backup_router, prefix="/api/backup")

    asyncio.create_task(worker.run())

    # Static file serving (React build)
    dist_dir = Path(__file__).parent.parent / "web" / "dist"
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 2: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 통과

- [ ] **Step 3: 서버 시작 확인**

```bash
uv run uvicorn app.main:app --reload
```

확인:
```bash
curl http://localhost:8000/api/channel/characterai/categories
curl http://localhost:8000/api/backup/history
curl http://localhost:8000/health
```

- [ ] **Step 4: 커밋**

```bash
git add app/main.py
git commit -m "feat: register channel router + static file serving in main.py"
```
