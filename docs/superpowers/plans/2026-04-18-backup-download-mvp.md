# 게시글 백업 + 다운로드 MVP 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** arca.live 게시글을 오프라인에서 볼 수 있도록 HTML 백업 + 미디어 다운로드 시스템을 구현한다.

**Architecture:** SQLModel로 게시글/다운로드 상태를 추적하고, asyncio 기반 다운로드 큐가 도메인별 동시 실행/딜레이를 관리한다. HTML 내 미디어 URL을 로컬 경로로 치환하여 오프라인 브라우징을 지원한다.

**Tech Stack:** Python 3.14, SQLModel, SQLite, asyncio, curl-cffi, BeautifulSoup4

**Spec:** `docs/superpowers/specs/2026-04-18-backup-download-mvp-design.md`

---

### Task 1: SQLModel 의존성 + DB 엔진 설정

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/engine.py`
- Create: `tests/db/__init__.py`
- Create: `tests/db/test_engine.py`

- [ ] **Step 1: sqlmodel 의존성 추가**

```bash
uv add sqlmodel
```

- [ ] **Step 2: 디렉토리 생성**

```bash
mkdir -p app/db tests/db
touch app/db/__init__.py tests/db/__init__.py
```

- [ ] **Step 3: 테스트 작성**

`tests/db/test_engine.py`:

```python
from pathlib import Path

from sqlmodel import Session, select

from app.db.engine import create_engine_and_tables, get_session


def test_create_engine_creates_db(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine_and_tables(f"sqlite:///{db_path}")
    assert db_path.exists()
    engine.dispose()


def test_get_session_returns_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine_and_tables(f"sqlite:///{db_path}")
    with get_session(engine) as session:
        assert isinstance(session, Session)
    engine.dispose()
```

- [ ] **Step 4: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/db/test_engine.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 5: engine.py 구현**

`app/db/engine.py`:

```python
from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine as sqlmodel_create_engine

load_dotenv()

DEFAULT_DB_URL = "sqlite:///data/sentinel.db"


def create_engine_and_tables(db_url: str | None = None):
    if db_url is None:
        db_url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    engine = sqlmodel_create_engine(db_url, echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@contextmanager
def get_session(engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
```

- [ ] **Step 6: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/db/test_engine.py -v
```

Expected: 2 passed

- [ ] **Step 7: 커밋**

```bash
git add app/db/ tests/db/ && git commit -m "feat: add SQLModel engine and session setup"
```

---

### Task 2: DB 모델 — Article, Download

**Files:**
- Create: `app/db/models.py`
- Create: `tests/db/test_models.py`

- [ ] **Step 1: 테스트 작성**

`tests/db/test_models.py`:

```python
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.db.engine import create_engine_and_tables
from app.db.models import Article, Download


def _engine(tmp_path):
    return create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")


def test_create_article(tmp_path):
    engine = _engine(tmp_path)
    article = Article(
        id=168039133,
        channel_slug="characterai",
        title="테스트 게시글",
        author="Wnfow",
        category="에셋·모듈봇",
        created_at=datetime(2026, 4, 18, 6, 43, 29, tzinfo=timezone.utc),
        url="https://arca.live/b/characterai/168039133",
    )
    with Session(engine) as session:
        session.add(article)
        session.commit()
        session.refresh(article)
        assert article.id == 168039133
        assert article.backup_status == "pending"
        assert article.backup_error is None
        assert article.backed_up_at is None
    engine.dispose()


def test_create_download(tmp_path):
    engine = _engine(tmp_path)
    article = Article(
        id=168039133,
        channel_slug="characterai",
        title="테스트",
        author="작성자",
        created_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        url="https://arca.live/b/characterai/168039133",
    )
    download = Download(
        article_id=168039133,
        url="https://ac-p3.namu.la/img.png",
        local_path="articles/168039133/images/img.png",
        file_type="image",
    )
    with Session(engine) as session:
        session.add(article)
        session.add(download)
        session.commit()
        session.refresh(download)
        assert download.id is not None
        assert download.status == "pending"
        assert download.error is None
    engine.dispose()


def test_article_downloads_relationship(tmp_path):
    engine = _engine(tmp_path)
    article = Article(
        id=100,
        channel_slug="test",
        title="t",
        author="a",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        url="https://arca.live/b/test/100",
    )
    d1 = Download(article_id=100, url="https://x/1.png", local_path="a/1.png", file_type="image")
    d2 = Download(article_id=100, url="https://x/2.mp4", local_path="a/2.mp4", file_type="video")
    with Session(engine) as session:
        session.add(article)
        session.add(d1)
        session.add(d2)
        session.commit()

        result = session.exec(select(Download).where(Download.article_id == 100)).all()
        assert len(result) == 2
        types = {d.file_type for d in result}
        assert types == {"image", "video"}
    engine.dispose()
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/db/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: models.py 구현**

`app/db/models.py`:

```python
from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class Article(SQLModel, table=True):
    id: int = Field(primary_key=True)
    channel_slug: str
    title: str
    author: str
    category: str | None = None
    created_at: datetime
    url: str
    backup_status: str = Field(default="pending")
    backup_error: str | None = None
    backed_up_at: datetime | None = None


class Download(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="article.id")
    url: str
    local_path: str
    file_type: str  # "image" | "video" | "audio" | "emoticon"
    status: str = Field(default="pending")
    error: str | None = None
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/db/test_models.py -v
```

Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add app/db/models.py tests/db/test_models.py && git commit -m "feat: add Article and Download DB models"
```

---

### Task 3: DB Repository — CRUD 함수

**Files:**
- Create: `app/db/repository.py`
- Create: `tests/db/test_repository.py`

- [ ] **Step 1: 테스트 작성**

`tests/db/test_repository.py`:

```python
from datetime import datetime, timezone

from sqlmodel import Session

from app.db.engine import create_engine_and_tables
from app.db.models import Article, Download
from app.db.repository import (
    create_article,
    get_article,
    update_article_status,
    create_download,
    get_downloads_for_article,
    update_download_status,
    is_article_completed,
)


def _session(tmp_path):
    engine = create_engine_and_tables(f"sqlite:///{tmp_path / 'test.db'}")
    return Session(engine)


def test_create_and_get_article(tmp_path):
    with _session(tmp_path) as session:
        art = create_article(
            session,
            id=100,
            channel_slug="test",
            title="제목",
            author="작성자",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            url="https://arca.live/b/test/100",
        )
        assert art.id == 100
        fetched = get_article(session, 100)
        assert fetched is not None
        assert fetched.title == "제목"


def test_get_article_not_found(tmp_path):
    with _session(tmp_path) as session:
        assert get_article(session, 999) is None


def test_update_article_status(tmp_path):
    with _session(tmp_path) as session:
        create_article(
            session, id=100, channel_slug="t", title="t", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            url="https://arca.live/b/t/100",
        )
        update_article_status(session, 100, "completed")
        art = get_article(session, 100)
        assert art.backup_status == "completed"
        assert art.backed_up_at is not None


def test_update_article_status_failed(tmp_path):
    with _session(tmp_path) as session:
        create_article(
            session, id=100, channel_slug="t", title="t", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            url="https://arca.live/b/t/100",
        )
        update_article_status(session, 100, "failed", error="3 files failed")
        art = get_article(session, 100)
        assert art.backup_status == "failed"
        assert art.backup_error == "3 files failed"


def test_create_and_get_downloads(tmp_path):
    with _session(tmp_path) as session:
        create_article(
            session, id=100, channel_slug="t", title="t", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            url="https://arca.live/b/t/100",
        )
        create_download(session, article_id=100, url="https://x/1.png", local_path="a/1.png", file_type="image")
        create_download(session, article_id=100, url="https://x/2.mp4", local_path="a/2.mp4", file_type="video")
        downloads = get_downloads_for_article(session, 100)
        assert len(downloads) == 2


def test_update_download_status(tmp_path):
    with _session(tmp_path) as session:
        create_article(
            session, id=100, channel_slug="t", title="t", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            url="https://arca.live/b/t/100",
        )
        dl = create_download(session, article_id=100, url="https://x/1.png", local_path="a/1.png", file_type="image")
        update_download_status(session, dl.id, "completed")
        downloads = get_downloads_for_article(session, 100)
        assert downloads[0].status == "completed"


def test_is_article_completed(tmp_path):
    with _session(tmp_path) as session:
        create_article(
            session, id=100, channel_slug="t", title="t", author="a",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            url="https://arca.live/b/t/100",
        )
        assert is_article_completed(session, 100) is False
        update_article_status(session, 100, "completed")
        assert is_article_completed(session, 100) is True
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/db/test_repository.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: repository.py 구현**

`app/db/repository.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.db.models import Article, Download


def create_article(
    session: Session,
    *,
    id: int,
    channel_slug: str,
    title: str,
    author: str,
    created_at: datetime,
    url: str,
    category: str | None = None,
) -> Article:
    article = Article(
        id=id,
        channel_slug=channel_slug,
        title=title,
        author=author,
        category=category,
        created_at=created_at,
        url=url,
    )
    session.add(article)
    session.commit()
    session.refresh(article)
    return article


def get_article(session: Session, article_id: int) -> Article | None:
    return session.get(Article, article_id)


def update_article_status(
    session: Session,
    article_id: int,
    status: str,
    *,
    error: str | None = None,
) -> None:
    article = session.get(Article, article_id)
    if article is None:
        return
    article.backup_status = status
    article.backup_error = error
    if status == "completed":
        article.backed_up_at = datetime.now(timezone.utc)
    session.add(article)
    session.commit()


def is_article_completed(session: Session, article_id: int) -> bool:
    article = session.get(Article, article_id)
    if article is None:
        return False
    return article.backup_status == "completed"


def create_download(
    session: Session,
    *,
    article_id: int,
    url: str,
    local_path: str,
    file_type: str,
) -> Download:
    download = Download(
        article_id=article_id,
        url=url,
        local_path=local_path,
        file_type=file_type,
    )
    session.add(download)
    session.commit()
    session.refresh(download)
    return download


def get_downloads_for_article(session: Session, article_id: int) -> list[Download]:
    statement = select(Download).where(Download.article_id == article_id)
    return list(session.exec(statement).all())


def update_download_status(
    session: Session,
    download_id: int,
    status: str,
    *,
    error: str | None = None,
) -> None:
    download = session.get(Download, download_id)
    if download is None:
        return
    download.status = status
    download.error = error
    session.add(download)
    session.commit()
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/db/test_repository.py -v
```

Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add app/db/repository.py tests/db/test_repository.py && git commit -m "feat: add Article/Download repository CRUD functions"
```

---

### Task 4: 미디어 추출 — HTML에서 미디어 URL 수집

**Files:**
- Create: `app/backup/__init__.py`
- Create: `app/backup/media.py`
- Create: `tests/backup/__init__.py`
- Create: `tests/backup/test_media.py`

- [ ] **Step 1: 디렉토리 생성**

```bash
mkdir -p app/backup tests/backup
touch app/backup/__init__.py tests/backup/__init__.py
```

- [ ] **Step 2: 테스트 작성**

`tests/backup/test_media.py`:

```python
from app.backup.media import MediaItem, extract_media_from_html, replace_urls_in_html


def test_extract_images():
    html = '''
    <div class="article-content">
        <img src="//ac-p3.namu.la/20260418sac/abc123.png?expires=123&key=abc" width="800" height="600">
        <img src="//ac-p3.namu.la/20260418sac/def456.webp?expires=123&key=def" width="400" height="300">
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 2
    assert all(i.file_type == "image" for i in items)
    assert items[0].url.startswith("https://")
    assert items[0].local_path == "articles/100/images/abc123.png"
    assert items[1].local_path == "articles/100/images/def456.webp"


def test_extract_emoticons():
    html = '''
    <div class="article-content">
        <img class="arca-emoticon" data-id="227952228" src="//ac-p3.namu.la/emote.png?expires=1&key=x" width="100" height="100">
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "emoticon"
    assert items[0].local_path == "emoticons/227952228.png"


def test_extract_video():
    html = '''
    <div class="article-content">
        <video>
            <source src="//ac-p3.namu.la/video123.mp4?expires=1&key=x">
        </video>
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "video"
    assert items[0].local_path == "articles/100/videos/video123.mp4"


def test_extract_audio():
    html = '''
    <div class="article-content">
        <audio src="//ac-p3.namu.la/sound456.mp3?expires=1&key=x"></audio>
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "audio"
    assert items[0].local_path == "articles/100/audio/sound456.mp3"


def test_extract_gif_is_image():
    html = '''
    <div class="article-content">
        <img src="//ac-p3.namu.la/anim.gif?expires=1&key=x">
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1
    assert items[0].file_type == "image"
    assert items[0].local_path == "articles/100/images/anim.gif"


def test_extract_deduplicates():
    html = '''
    <div class="article-content">
        <img src="//ac-p3.namu.la/same.png?expires=1&key=x">
        <img src="//ac-p3.namu.la/same.png?expires=2&key=y">
    </div>
    '''
    items = extract_media_from_html(html, article_id=100)
    assert len(items) == 1


def test_replace_urls_in_html():
    html = '<img src="//ac-p3.namu.la/abc.png?expires=1&amp;key=x">'
    url_map = {
        "https://ac-p3.namu.la/abc.png?expires=1&key=x": "./images/abc.png",
    }
    result = replace_urls_in_html(html, url_map)
    assert "./images/abc.png" in result
    assert "namu.la" not in result


def test_replace_urls_emoticon_relative_path():
    html = '<img class="arca-emoticon" data-id="123" src="//ac-p3.namu.la/emote.png?expires=1&amp;key=x">'
    url_map = {
        "https://ac-p3.namu.la/emote.png?expires=1&key=x": "../../emoticons/123.png",
    }
    result = replace_urls_in_html(html, url_map)
    assert "../../emoticons/123.png" in result
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/backup/test_media.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: media.py 구현**

`app/backup/media.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse

from bs4 import BeautifulSoup

VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi"}
AUDIO_EXTS = {".mp3", ".ogg", ".wav", ".flac", ".m4a"}


@dataclass
class MediaItem:
    url: str             # 원본 URL (https://...)
    local_path: str      # data/ 기준 상대 경로
    file_type: str       # "image" | "video" | "audio" | "emoticon"
    relative_path: str   # backup.html 기준 상대 경로 (HTML 치환용)


def extract_media_from_html(html: str, article_id: int) -> list[MediaItem]:
    soup = BeautifulSoup(html, "lxml")
    items: list[MediaItem] = []
    seen_urls: set[str] = set()

    # img 태그
    for img in soup.select("img"):
        src = img.get("src", "")
        if not src:
            continue
        url = _normalize_url(src)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        if "arca-emoticon" in img.get("class", []):
            data_id = img.get("data-id", "")
            ext = _get_ext(url)
            local_path = f"emoticons/{data_id}{ext}"
            relative_path = f"../../emoticons/{data_id}{ext}"
            items.append(MediaItem(url=url, local_path=local_path, file_type="emoticon", relative_path=relative_path))
        else:
            filename = _get_filename(url)
            file_type = _classify_ext(_get_ext(url))
            subdir = _subdir_for_type(file_type)
            local_path = f"articles/{article_id}/{subdir}/{filename}"
            relative_path = f"./{subdir}/{filename}"
            items.append(MediaItem(url=url, local_path=local_path, file_type=file_type, relative_path=relative_path))

    # video 태그
    for vid in soup.select("video source, video[src]"):
        src = vid.get("src", "")
        if not src:
            continue
        url = _normalize_url(src)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        filename = _get_filename(url)
        local_path = f"articles/{article_id}/videos/{filename}"
        relative_path = f"./videos/{filename}"
        items.append(MediaItem(url=url, local_path=local_path, file_type="video", relative_path=relative_path))

    # audio 태그
    for aud in soup.select("audio[src], audio source"):
        src = aud.get("src", "")
        if not src:
            continue
        url = _normalize_url(src)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        filename = _get_filename(url)
        local_path = f"articles/{article_id}/audio/{filename}"
        relative_path = f"./audio/{filename}"
        items.append(MediaItem(url=url, local_path=local_path, file_type="audio", relative_path=relative_path))

    return items


def replace_urls_in_html(html: str, url_map: dict[str, str]) -> str:
    for original_url, local_path in url_map.items():
        # HTML에서는 &amp;로 인코딩될 수 있음
        parsed = urlparse(original_url)
        # //도메인/경로 형태의 원본도 치환
        src_variant_proto = f"//{parsed.netloc}{parsed.path}"
        if parsed.query:
            src_variant_proto += f"?{parsed.query}"

        html = html.replace(src_variant_proto, local_path)
        html = html.replace(src_variant_proto.replace("&", "&amp;"), local_path)
        html = html.replace(original_url, local_path)

    return html


def _normalize_url(src: str) -> str:
    if src.startswith("//"):
        return f"https:{src}"
    return src


def _get_ext(url: str) -> str:
    path = urlparse(url).path
    return PurePosixPath(path).suffix


def _get_filename(url: str) -> str:
    path = urlparse(url).path
    return PurePosixPath(path).name


def _classify_ext(ext: str) -> str:
    ext_lower = ext.lower()
    if ext_lower in VIDEO_EXTS:
        return "video"
    if ext_lower in AUDIO_EXTS:
        return "audio"
    return "image"


def _subdir_for_type(file_type: str) -> str:
    if file_type == "video":
        return "videos"
    if file_type == "audio":
        return "audio"
    return "images"
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/backup/test_media.py -v
```

Expected: 9 passed

- [ ] **Step 6: 커밋**

```bash
git add app/backup/ tests/backup/ && git commit -m "feat: add media extraction and URL replacement for HTML backup"
```

---

### Task 5: 다운로드 큐 — 도메인별 동시 실행 + 딜레이

**Files:**
- Create: `app/backup/queue.py`
- Create: `tests/backup/test_queue.py`

- [ ] **Step 1: 테스트 작성**

`tests/backup/test_queue.py`:

```python
import asyncio
import time

from app.backup.queue import DomainConfig, DownloadQueue


def test_domain_config_defaults():
    q = DownloadQueue()
    cfg = q.get_domain_config("unknown.com")
    assert cfg.concurrency == 2
    assert cfg.delay == 1.0


def test_domain_config_arca():
    q = DownloadQueue()
    cfg = q.get_domain_config("arca.live")
    assert cfg.concurrency == 1
    assert cfg.delay == 3.0


def test_domain_config_namu():
    q = DownloadQueue()
    cfg = q.get_domain_config("ac-p3.namu.la")
    assert cfg.concurrency == 3
    assert cfg.delay == 1.0


def test_domain_config_custom():
    overrides = {"example.com": DomainConfig(concurrency=5, delay=0.5)}
    q = DownloadQueue(domain_overrides=overrides)
    cfg = q.get_domain_config("example.com")
    assert cfg.concurrency == 5
    assert cfg.delay == 0.5


def test_download_executes_task():
    q = DownloadQueue()
    results = []

    async def fake_download(url: str, dest: str):
        results.append((url, dest))

    async def run():
        await q.submit("https://ac-p3.namu.la/img.png", "/tmp/img.png", fake_download)
        await q.wait_all()

    asyncio.run(run())
    assert len(results) == 1
    assert results[0] == ("https://ac-p3.namu.la/img.png", "/tmp/img.png")


def test_download_respects_delay():
    q = DownloadQueue(
        domain_overrides={"ac-p3.namu.la": DomainConfig(concurrency=1, delay=0.3)}
    )
    timestamps = []

    async def timed_download(url: str, dest: str):
        timestamps.append(time.monotonic())

    async def run():
        for i in range(3):
            await q.submit(f"https://ac-p3.namu.la/{i}.png", f"/tmp/{i}.png", timed_download)
        await q.wait_all()

    asyncio.run(run())
    assert len(timestamps) == 3
    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i - 1]
        assert gap >= 0.25, f"Gap {gap} too short, expected >= 0.25s"


def test_download_concurrency_limit():
    q = DownloadQueue(
        domain_overrides={"ac-p3.namu.la": DomainConfig(concurrency=2, delay=0.0)}
    )
    max_concurrent = 0
    current = 0
    lock = asyncio.Lock()

    async def track_concurrency(url: str, dest: str):
        nonlocal max_concurrent, current
        async with lock:
            current += 1
            if current > max_concurrent:
                max_concurrent = current
        await asyncio.sleep(0.1)
        async with lock:
            current -= 1

    async def run():
        for i in range(5):
            await q.submit(f"https://ac-p3.namu.la/{i}.png", f"/tmp/{i}.png", track_concurrency)
        await q.wait_all()

    asyncio.run(run())
    assert max_concurrent <= 2
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/backup/test_queue.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: queue.py 구현**

`app/backup/queue.py`:

```python
from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


@dataclass
class DomainConfig:
    concurrency: int = 2
    delay: float = 1.0


# 기본 도메인 설정
_DEFAULT_CONFIGS: dict[str, DomainConfig] = {
    "arca.live": DomainConfig(
        concurrency=int(os.environ.get("DOWNLOAD_ARCA_LIVE_CONCURRENCY", "1")),
        delay=float(os.environ.get("DOWNLOAD_ARCA_LIVE_DELAY", "3")),
    ),
    "namu.la": DomainConfig(
        concurrency=int(os.environ.get("DOWNLOAD_NAMU_LA_CONCURRENCY", "3")),
        delay=float(os.environ.get("DOWNLOAD_NAMU_LA_DELAY", "1")),
    ),
}

_DEFAULT_FALLBACK = DomainConfig(
    concurrency=int(os.environ.get("DOWNLOAD_DEFAULT_CONCURRENCY", "2")),
    delay=float(os.environ.get("DOWNLOAD_DEFAULT_DELAY", "1")),
)


class DownloadQueue:
    def __init__(self, domain_overrides: dict[str, DomainConfig] | None = None):
        self._configs: dict[str, DomainConfig] = {**_DEFAULT_CONFIGS}
        if domain_overrides:
            self._configs.update(domain_overrides)
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._last_request: dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()
        self._tasks: list[asyncio.Task] = []

    def get_domain_config(self, domain: str) -> DomainConfig:
        # 정확한 도메인 매칭 우선
        if domain in self._configs:
            return self._configs[domain]
        # 서브도메인 매칭 (ac-p3.namu.la → namu.la)
        for key, cfg in self._configs.items():
            if domain.endswith(f".{key}") or domain == key:
                return cfg
        return _DEFAULT_FALLBACK

    def _get_semaphore(self, domain_key: str, concurrency: int) -> asyncio.Semaphore:
        if domain_key not in self._semaphores:
            self._semaphores[domain_key] = asyncio.Semaphore(concurrency)
        return self._semaphores[domain_key]

    def _domain_key(self, domain: str) -> str:
        # 서브도메인을 기본 도메인으로 통합
        for key in self._configs:
            if domain.endswith(f".{key}") or domain == key:
                return key
        return domain

    async def submit(
        self,
        url: str,
        dest: str,
        download_fn: Callable[[str, str], Awaitable[None]],
    ) -> None:
        domain = urlparse(url).netloc
        domain_key = self._domain_key(domain)
        config = self.get_domain_config(domain)
        sem = self._get_semaphore(domain_key, config.concurrency)

        async def _run():
            async with sem:
                async with self._lock:
                    last = self._last_request[domain_key]
                    now = time.monotonic()
                    wait = config.delay - (now - last)
                    if wait > 0:
                        # lock 해제 후 대기
                        self._last_request[domain_key] = now + wait
                    else:
                        self._last_request[domain_key] = now

                if wait > 0:
                    await asyncio.sleep(wait)

                await download_fn(url, dest)

        task = asyncio.create_task(_run())
        self._tasks.append(task)

    async def wait_all(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks)
            self._tasks.clear()
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/backup/test_queue.py -v
```

Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add app/backup/queue.py tests/backup/test_queue.py && git commit -m "feat: add download queue with per-domain concurrency and delay"
```

---

### Task 6: 백업 서비스 — 오케스트레이션

**Files:**
- Create: `app/backup/service.py`
- Create: `tests/backup/test_service.py`

- [ ] **Step 1: 테스트 작성**

`tests/backup/test_service.py`:

```python
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlmodel import Session

from app.backup.service import BackupService
from app.db.engine import create_engine_and_tables
from app.db.models import Article, Download
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
        <img class="arca-emoticon" data-id="9999" src="//ac-p3.namu.la/emote.png?expires=1&key=x" width="100">
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

    service = BackupService(engine=engine, client=mock_client, data_dir=str(data_dir))
    return engine, service, data_dir


def test_backup_creates_article_record(tmp_path):
    engine, service, data_dir = _setup(tmp_path)

    asyncio.run(service.backup_article(
        article_id=100,
        channel_slug="test",
    ))

    with Session(engine) as session:
        art = get_article(session, 100)
        assert art is not None
        assert art.title == "테스트 게시글"
        assert art.backup_status == "completed"
    engine.dispose()


def test_backup_downloads_media(tmp_path):
    engine, service, data_dir = _setup(tmp_path)

    asyncio.run(service.backup_article(
        article_id=100,
        channel_slug="test",
    ))

    with Session(engine) as session:
        downloads = get_downloads_for_article(session, 100)
        assert len(downloads) == 2  # 1 image + 1 emoticon
        statuses = {d.status for d in downloads}
        assert statuses == {"completed"}
    engine.dispose()


def test_backup_creates_html_file(tmp_path):
    engine, service, data_dir = _setup(tmp_path)

    asyncio.run(service.backup_article(
        article_id=100,
        channel_slug="test",
    ))

    backup_html = data_dir / "articles" / "100" / "backup.html"
    assert backup_html.exists()
    content = backup_html.read_text()
    assert "namu.la" not in content  # URL이 로컬 경로로 치환됨
    engine.dispose()


def test_backup_skips_completed(tmp_path):
    engine, service, data_dir = _setup(tmp_path)

    asyncio.run(service.backup_article(article_id=100, channel_slug="test"))
    call_count_before = service._client.get.call_count

    asyncio.run(service.backup_article(article_id=100, channel_slug="test"))
    call_count_after = service._client.get.call_count

    assert call_count_after == call_count_before  # 추가 호출 없음
    engine.dispose()


def test_backup_force_redownload(tmp_path):
    engine, service, data_dir = _setup(tmp_path)

    asyncio.run(service.backup_article(article_id=100, channel_slug="test"))
    call_count_before = service._client.get.call_count

    asyncio.run(service.backup_article(article_id=100, channel_slug="test", force=True))
    call_count_after = service._client.get.call_count

    assert call_count_after > call_count_before
    engine.dispose()
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/backup/test_service.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: service.py 구현**

`app/backup/service.py`:

```python
from __future__ import annotations

import asyncio
from pathlib import Path

from sqlmodel import Session

from app.backup.media import MediaItem, extract_media_from_html, replace_urls_in_html
from app.backup.queue import DownloadQueue
from app.db.engine import get_session
from app.db.models import Article
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
    ) -> None:
        with get_session(self._engine) as session:
            if not force and is_article_completed(session, article_id):
                return

            # 1. 상세 페이지 가져오기
            resp = await asyncio.to_thread(
                self._client.get, f"/b/{channel_slug}/{article_id}"
            )
            html = resp.text

            # 2. 메타 정보 파싱 + Article 레코드
            detail = parse_article_detail(html, article_id)
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

        # 3. 미디어 추출
        media_items = extract_media_from_html(html, article_id)

        # 4. Download 레코드 생성
        with get_session(self._engine) as session:
            # force인 경우 기존 다운로드 레코드의 상태를 리셋
            if force:
                for dl in get_downloads_for_article(session, article_id):
                    update_download_status(session, dl.id, "pending")

            for item in media_items:
                existing = get_downloads_for_article(session, article_id)
                urls = {d.url for d in existing}
                if item.url not in urls:
                    create_download(
                        session,
                        article_id=article_id,
                        url=item.url,
                        local_path=item.local_path,
                        file_type=item.file_type,
                    )

        # 5. 다운로드 실행
        failed_count = 0
        url_to_relative: dict[str, str] = {}

        for item in media_items:
            url_to_relative[item.url] = item.relative_path
            dest = self._data_dir / item.local_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            # 이모티콘은 이미 있으면 스킵
            if item.file_type == "emoticon" and dest.exists():
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "completed")
                            break
                continue

            try:
                file_resp = await asyncio.to_thread(self._client.get, item.url)
                dest.write_bytes(file_resp.content)
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "completed")
                            break
            except Exception as e:
                failed_count += 1
                with get_session(self._engine) as session:
                    for dl in get_downloads_for_article(session, article_id):
                        if dl.url == item.url:
                            update_download_status(session, dl.id, "failed", error=str(e))
                            break

        # 6. HTML 치환 + 저장
        backup_html = replace_urls_in_html(html, url_to_relative)
        backup_path = self._data_dir / "articles" / str(article_id) / "backup.html"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(backup_html, encoding="utf-8")

        # 7. 최종 상태
        with get_session(self._engine) as session:
            if failed_count > 0:
                update_article_status(
                    session, article_id, "failed",
                    error=f"{failed_count} file(s) failed to download",
                )
            else:
                update_article_status(session, article_id, "completed")
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/backup/test_service.py -v
```

Expected: 5 passed

- [ ] **Step 5: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 통과

- [ ] **Step 6: 커밋**

```bash
git add app/backup/service.py tests/backup/test_service.py && git commit -m "feat: add BackupService — article backup orchestration"
```

---

### Task 7: .env.example 업데이트 + 공개 API

**Files:**
- Modify: `.env.example`
- Modify: `app/db/__init__.py`
- Modify: `app/backup/__init__.py`

- [ ] **Step 1: .env.example 업데이트**

`.env.example`:

```
ARCA_COOKIES="arca.nick=...; arca.at=...; ..."

DATABASE_URL="sqlite:///data/sentinel.db"

DOWNLOAD_ARCA_LIVE_CONCURRENCY=1
DOWNLOAD_ARCA_LIVE_DELAY=3
DOWNLOAD_NAMU_LA_CONCURRENCY=3
DOWNLOAD_NAMU_LA_DELAY=1
DOWNLOAD_DEFAULT_CONCURRENCY=2
DOWNLOAD_DEFAULT_DELAY=1
```

- [ ] **Step 2: app/db/__init__.py export**

`app/db/__init__.py`:

```python
from app.db.engine import create_engine_and_tables, get_session
from app.db.models import Article, Download
from app.db.repository import (
    create_article,
    create_download,
    get_article,
    get_downloads_for_article,
    is_article_completed,
    update_article_status,
    update_download_status,
)

__all__ = [
    "create_engine_and_tables",
    "get_session",
    "Article",
    "Download",
    "create_article",
    "create_download",
    "get_article",
    "get_downloads_for_article",
    "is_article_completed",
    "update_article_status",
    "update_download_status",
]
```

- [ ] **Step 3: app/backup/__init__.py export**

`app/backup/__init__.py`:

```python
from app.backup.service import BackupService

__all__ = ["BackupService"]
```

- [ ] **Step 4: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 통과

- [ ] **Step 5: import 확인**

```bash
uv run python -c "
from app.db import create_engine_and_tables, Article, Download
from app.backup import BackupService
print('All imports OK')
"
```

- [ ] **Step 6: .gitignore에 data/ 추가**

```bash
echo "data/" >> .gitignore
```

- [ ] **Step 7: 커밋**

```bash
git add .env.example app/db/__init__.py app/backup/__init__.py .gitignore && git commit -m "feat: public API exports and env config for backup system"
```
