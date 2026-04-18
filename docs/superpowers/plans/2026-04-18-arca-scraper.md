# arca.live 스크래퍼 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** arca.live 채널의 조회 기능(목록, 검색, 상세, 댓글)을 Python 라이브러리로 구현한다.

**Architecture:** `ArcaClient`(HTTP) → `ArcaChannel`(API 진입점) → `parser.py`(HTML→모델). 모든 데이터는 Pydantic 모델로 반환. 기존 `client.py`를 리팩터링하고, `parser.py`를 재작성하며, `models.py`와 `channel.py`를 신규 생성한다.

**Tech Stack:** Python 3.14, curl-cffi, BeautifulSoup4/lxml, Pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-04-18-arca-scraper-design.md`

---

### Task 1: 프로젝트 테스트 인프라 + Pydantic 모델 정의

**Files:**
- Create: `app/scraper/arca/models.py`
- Create: `tests/__init__.py`
- Create: `tests/scraper/__init__.py`
- Create: `tests/scraper/arca/__init__.py`
- Create: `tests/scraper/arca/test_models.py`

- [ ] **Step 1: pytest 의존성 추가**

```bash
uv add --dev pytest
```

- [ ] **Step 2: 테스트 디렉토리 생성**

```bash
mkdir -p tests/scraper/arca
touch tests/__init__.py tests/scraper/__init__.py tests/scraper/arca/__init__.py
```

- [ ] **Step 3: 모델 검증 테스트 작성**

`tests/scraper/arca/test_models.py`:

```python
from datetime import datetime, timezone

from app.scraper.arca.models import (
    ArticleDetail,
    ArticleList,
    ArticleRow,
    Attachment,
    Category,
    Comment,
)


def test_category():
    cat = Category(name="일반", slug="%EC%9D%BC%EB%B0%98")
    assert cat.name == "일반"
    assert cat.slug == "%EC%9D%BC%EB%B0%98"


def test_article_row():
    row = ArticleRow(
        id=599677,
        title="테스트 게시글",
        category="일반",
        comment_count=5,
        author="ㅇㅇ",
        created_at=datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc),
        view_count=100,
        vote_count=10,
        has_image=True,
        has_video=False,
        url="https://arca.live/b/characterai/599677",
    )
    assert row.id == 599677
    assert row.has_image is True


def test_article_list():
    al = ArticleList(articles=[], current_page=1, total_pages=10)
    assert al.current_page == 1
    assert al.articles == []


def test_attachment():
    att = Attachment(url="https://ac-p3.namu.la/img.png", media_type="image")
    assert att.media_type == "image"


def test_article_detail():
    detail = ArticleDetail(
        id=168046805,
        title="테스트",
        category="일반",
        author="작성자",
        created_at=datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc),
        view_count=73,
        vote_count=0,
        down_vote_count=0,
        comment_count=0,
        content_html="<p>본문</p>",
        attachments=[],
    )
    assert detail.id == 168046805


def test_comment_with_replies():
    reply = Comment(
        id="c_2",
        author="답글러",
        content_html="<p>답글</p>",
        created_at=datetime(2026, 4, 18, 8, 1, 0, tzinfo=timezone.utc),
    )
    parent = Comment(
        id="c_1",
        author="원댓러",
        content_html="<p>원댓</p>",
        created_at=datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc),
        replies=[reply],
    )
    assert len(parent.replies) == 1
    assert parent.replies[0].id == "c_2"
```

- [ ] **Step 4: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/scraper/arca/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.scraper.arca.models'`

- [ ] **Step 5: models.py 구현**

`app/scraper/arca/models.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Category(BaseModel):
    name: str
    slug: str


class ArticleRow(BaseModel):
    id: int
    title: str
    category: str | None
    comment_count: int
    author: str
    created_at: datetime
    view_count: int
    vote_count: int
    has_image: bool
    has_video: bool
    url: str


class ArticleList(BaseModel):
    articles: list[ArticleRow]
    current_page: int
    total_pages: int


class Attachment(BaseModel):
    url: str
    media_type: str  # "image" | "video"


class ArticleDetail(BaseModel):
    id: int
    title: str
    category: str | None
    author: str
    created_at: datetime
    view_count: int
    vote_count: int
    down_vote_count: int
    comment_count: int
    content_html: str
    attachments: list[Attachment]


class Comment(BaseModel):
    id: str
    author: str
    content_html: str
    created_at: datetime
    replies: list[Comment] = []
```

- [ ] **Step 6: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/scraper/arca/test_models.py -v
```

Expected: 6 passed

- [ ] **Step 7: 커밋**

```bash
git add app/scraper/arca/models.py tests/
git commit -m "feat: add Pydantic models and test infrastructure"
```

---

### Task 2: ArcaClient .env 쿠키 자동 로드

**Files:**
- Modify: `app/scraper/arca/client.py`
- Create: `tests/scraper/arca/test_client.py`

- [ ] **Step 1: 테스트 작성**

`tests/scraper/arca/test_client.py`:

```python
import os

from app.scraper.arca.client import ArcaClient


def test_client_with_explicit_cookies():
    client = ArcaClient(cookies="foo=bar; baz=qux")
    assert client.session.cookies.get("foo", domain="arca.live") == "bar"
    assert client.session.cookies.get("baz", domain="arca.live") == "qux"
    client.close()


def test_client_with_empty_cookies():
    client = ArcaClient(cookies="")
    assert client.session is not None
    client.close()


def test_client_loads_from_env(monkeypatch):
    monkeypatch.setenv("ARCA_COOKIES", "envkey=envval; another=thing")
    client = ArcaClient()
    assert client.session.cookies.get("envkey", domain="arca.live") == "envval"
    assert client.session.cookies.get("another", domain="arca.live") == "thing"
    client.close()


def test_client_no_cookies_no_env(monkeypatch):
    monkeypatch.delenv("ARCA_COOKIES", raising=False)
    client = ArcaClient()
    assert client.session is not None
    client.close()
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/scraper/arca/test_client.py -v
```

Expected: FAIL — `TypeError: ArcaClient.__init__() missing 1 required positional argument: 'cookies'`

- [ ] **Step 3: client.py 수정 — cookies를 Optional로, .env 폴백**

`app/scraper/arca/client.py` 전체:

```python
from __future__ import annotations

import os

from curl_cffi import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "ko,en-US;q=0.9,en;q=0.8",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "upgrade-insecure-requests": "1",
}

BASE_URL = "https://arca.live"


class ArcaClient:
    """curl-cffi 기반 arca.live 클라이언트. Cloudflare 우회를 위해 브라우저 impersonation 사용."""

    def __init__(self, cookies: str | None = None):
        """cookies: raw cookie 문자열. None이면 ARCA_COOKIES 환경변수에서 로드."""
        self.session = requests.Session(impersonate="chrome136")
        self.session.headers.update(DEFAULT_HEADERS)
        if cookies is None:
            cookies = os.environ.get("ARCA_COOKIES", "")
        self._set_cookies(cookies)

    def _set_cookies(self, raw: str):
        for pair in raw.split(";"):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            self.session.cookies.set(key.strip(), value.strip(), domain="arca.live")

    def get(self, path: str, **kwargs) -> requests.Response:
        url = f"{BASE_URL}{path}" if path.startswith("/") else path
        resp = self.session.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def close(self):
        self.session.close()
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/scraper/arca/test_client.py -v
```

Expected: 4 passed

- [ ] **Step 5: .env.example 생성**

`.env.example`:

```
ARCA_COOKIES="arca.nick=...; arca.at=...; ..."
```

- [ ] **Step 6: .gitignore에 .env 추가 확인**

```bash
grep -q "^\.env$" .gitignore || echo ".env" >> .gitignore
```

- [ ] **Step 7: 커밋**

```bash
git add app/scraper/arca/client.py tests/scraper/arca/test_client.py .env.example .gitignore
git commit -m "feat: ArcaClient auto-loads cookies from .env"
```

---

### Task 3: parser.py — 게시글 목록 + 페이지네이션 + 카테고리 파싱

기존 dataclass 기반 `parser.py`를 Pydantic 모델 기반으로 재작성.

**Files:**
- Rewrite: `app/scraper/arca/parser.py`
- Create: `tests/scraper/arca/test_parser_list.py`
- Create: `tests/scraper/arca/fixtures/article_list.html`

- [ ] **Step 1: HTML fixture 저장**

실제 arca.live에서 가져온 HTML을 fixture로 저장. 테스트 스크립트로 생성:

```bash
uv run python -c "
from app.scraper.arca.client import ArcaClient
import os, pathlib

cookies = os.environ.get('ARCA_COOKIES', '')
c = ArcaClient(cookies)
resp = c.get('/b/characterai')
path = pathlib.Path('tests/scraper/arca/fixtures')
path.mkdir(parents=True, exist_ok=True)
(path / 'article_list.html').write_text(resp.text, encoding='utf-8')
print(f'Saved {len(resp.text)} chars')
c.close()
"
```

- [ ] **Step 2: 테스트 작성**

`tests/scraper/arca/test_parser_list.py`:

```python
from pathlib import Path

from app.scraper.arca.models import ArticleList, ArticleRow, Category
from app.scraper.arca.parser import parse_article_list, parse_categories, parse_pagination

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_article_list_excludes_notices():
    html = _load("article_list.html")
    articles = parse_article_list(html)
    assert len(articles) > 0
    assert all(isinstance(a, ArticleRow) for a in articles)


def test_parse_article_row_fields():
    html = _load("article_list.html")
    articles = parse_article_list(html)
    a = articles[0]
    assert a.id > 0
    assert len(a.title) > 0
    assert len(a.author) > 0
    assert a.view_count >= 0
    assert a.vote_count >= 0
    assert a.url.startswith("https://arca.live")


def test_parse_categories():
    html = _load("article_list.html")
    cats = parse_categories(html)
    assert len(cats) > 0
    assert all(isinstance(c, Category) for c in cats)
    names = [c.name for c in cats]
    assert "전체" in names


def test_parse_pagination():
    html = _load("article_list.html")
    current, total = parse_pagination(html)
    assert current == 1
    assert total >= 1
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/scraper/arca/test_parser_list.py -v
```

Expected: FAIL — `ImportError: cannot import name 'parse_categories' from 'app.scraper.arca.parser'`

- [ ] **Step 4: parser.py 재작성**

`app/scraper/arca/parser.py`:

```python
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag

from app.scraper.arca.models import (
    ArticleDetail,
    ArticleRow,
    Attachment,
    Category,
    Comment,
)


# ---------------------------------------------------------------------------
# 게시글 목록
# ---------------------------------------------------------------------------

def parse_article_list(html: str) -> list[ArticleRow]:
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("a.vrow.column")
    articles: list[ArticleRow] = []
    for row in rows:
        classes = row.get("class", [])
        if "notice" in classes or "head" in classes:
            continue
        article = _parse_article_row(row)
        if article:
            articles.append(article)
    return articles


def _parse_article_row(row: Tag) -> ArticleRow | None:
    id_el = row.select_one(".col-id")
    if not id_el:
        return None
    try:
        article_id = int(id_el.get_text(strip=True))
    except ValueError:
        return None

    title_el = row.select_one(".col-title .title")
    title = title_el.get_text(strip=True) if title_el else ""

    badge_el = row.select_one(".col-title .badge")
    category = badge_el.get_text(strip=True) if badge_el else None

    comment_el = row.select_one(".col-title .comment-count")
    comment_count = 0
    if comment_el:
        m = re.search(r"\d+", comment_el.get_text())
        if m:
            comment_count = int(m.group())

    author_el = row.select_one(".col-author")
    author = author_el.get_text(strip=True) if author_el else ""

    time_el = row.select_one(".col-time time")
    created_at = datetime.min
    if time_el and time_el.get("datetime"):
        created_at = datetime.fromisoformat(
            time_el["datetime"].replace("Z", "+00:00")
        )

    view_count = _parse_int(row.select_one(".col-view"))
    vote_count = _parse_int(row.select_one(".col-rate"))

    has_image = bool(row.select_one(".media-icon.ion-ios-photos-outline"))
    has_video = bool(row.select_one(".media-icon.ion-ios-videocam-outline"))

    href = row.get("href", "")
    url = href if href.startswith("http") else f"https://arca.live{href}"

    return ArticleRow(
        id=article_id,
        title=title,
        category=category,
        comment_count=comment_count,
        author=author,
        created_at=created_at,
        view_count=view_count,
        vote_count=vote_count,
        has_image=has_image,
        has_video=has_video,
        url=url,
    )


# ---------------------------------------------------------------------------
# 카테고리 탭
# ---------------------------------------------------------------------------

def parse_categories(html: str) -> list[Category]:
    soup = BeautifulSoup(html, "lxml")
    cats: list[Category] = []
    for a in soup.select(".board-category a"):
        name = a.get_text(strip=True)
        href = a.get("href", "")
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        slug = qs.get("category", [""])[0]
        cats.append(Category(name=name, slug=slug))
    return cats


# ---------------------------------------------------------------------------
# 페이지네이션
# ---------------------------------------------------------------------------

def parse_pagination(html: str) -> tuple[int, int]:
    """Returns (current_page, total_pages)."""
    soup = BeautifulSoup(html, "lxml")
    pages = soup.select(".pagination-wrapper .pagination a")
    if not pages:
        return 1, 1

    current = 1
    total = 1
    for a in pages:
        href = a.get("href", "")
        qs = parse_qs(urlparse(href).query)
        p_vals = qs.get("p", [])
        if not p_vals:
            continue
        try:
            p = int(p_vals[0])
        except ValueError:
            continue
        if p > total:
            total = p
        if "active" in a.parent.get("class", []):
            current = p

    # active 클래스가 li에 있을 수 있음
    active_li = soup.select_one(".pagination-wrapper .pagination .active a")
    if active_li:
        href = active_li.get("href", "")
        qs = parse_qs(urlparse(href).query)
        p_vals = qs.get("p", [])
        if p_vals:
            try:
                current = int(p_vals[0])
            except ValueError:
                pass

    return current, total


# ---------------------------------------------------------------------------
# 게시글 상세
# ---------------------------------------------------------------------------

def parse_article_detail(html: str, article_id: int) -> ArticleDetail:
    soup = BeautifulSoup(html, "lxml")
    head = soup.select_one(".article-head")

    # title — 카테고리 뱃지 뒤의 순수 제목
    title_el = head.select_one(".title") if head else None
    title = title_el.get_text(strip=True) if title_el else ""

    # category
    badge_el = head.select_one(".badge") if head else None
    category = badge_el.get_text(strip=True) if badge_el else None
    # title에서 category 텍스트 제거
    if category and title.startswith(category):
        title = title[len(category):].strip()

    # author
    author_el = head.select_one(".user-info") if head else None
    author = author_el.get_text(strip=True) if author_el else ""

    # info pairs: 추천/비추천/댓글/조회수/작성일
    info_map: dict[str, str] = {}
    if head:
        heads = head.select(".article-info .head")
        bodies = head.select(".article-info .body")
        for h, b in zip(heads, bodies):
            info_map[h.get_text(strip=True)] = b.get_text(strip=True)

    vote_count = _safe_int(info_map.get("추천", "0"))
    down_vote_count = _safe_int(info_map.get("비추천", "0"))
    comment_count = _safe_int(info_map.get("댓글", "0"))
    view_count = _safe_int(info_map.get("조회수", "0"))

    date_str = info_map.get("작성일", "")
    created_at = datetime.min
    if date_str:
        # article-info의 date는 time 태그 안에 있을 수 있음
        time_el = head.select_one(".article-info time") if head else None
        if time_el and time_el.get("datetime"):
            created_at = datetime.fromisoformat(
                time_el["datetime"].replace("Z", "+00:00")
            )
        else:
            try:
                created_at = datetime.fromisoformat(date_str)
            except ValueError:
                pass

    # content
    content_el = soup.select_one(".article-body .article-content")
    content_html = content_el.decode_contents() if content_el else ""

    # attachments
    attachments: list[Attachment] = []
    if content_el:
        for img in content_el.select("img"):
            src = img.get("src", "")
            if not src:
                continue
            # 이모티콘 제외
            if "arca-emoticon" in img.get("class", []):
                continue
            url = f"https:{src}" if src.startswith("//") else src
            attachments.append(Attachment(url=url, media_type="image"))
        for vid in content_el.select("video source, video"):
            src = vid.get("src", "")
            if not src:
                continue
            url = f"https:{src}" if src.startswith("//") else src
            attachments.append(Attachment(url=url, media_type="video"))

    return ArticleDetail(
        id=article_id,
        title=title,
        category=category,
        author=author,
        created_at=created_at,
        view_count=view_count,
        vote_count=vote_count,
        down_vote_count=down_vote_count,
        comment_count=comment_count,
        content_html=content_html,
        attachments=attachments,
    )


# ---------------------------------------------------------------------------
# 댓글
# ---------------------------------------------------------------------------

def parse_comments(html: str) -> list[Comment]:
    soup = BeautifulSoup(html, "lxml")
    comments: list[Comment] = []
    for wrapper in soup.select(".comment-wrapper"):
        items = wrapper.select(".comment-item")
        if not items:
            continue
        parent = _parse_comment_item(items[0])
        if not parent:
            continue
        for item in items[1:]:
            reply = _parse_comment_item(item)
            if reply:
                parent.replies.append(reply)
        comments.append(parent)
    return comments


def _parse_comment_item(el: Tag) -> Comment | None:
    comment_id = el.get("id", "")
    if not comment_id:
        return None

    author_el = el.select_one(".user-info")
    author = author_el.get_text(strip=True) if author_el else ""

    message_el = el.select_one(".message")
    content_html = message_el.decode_contents() if message_el else ""

    time_el = el.select_one("time")
    created_at = datetime.min
    if time_el and time_el.get("datetime"):
        created_at = datetime.fromisoformat(
            time_el["datetime"].replace("Z", "+00:00")
        )

    return Comment(
        id=comment_id,
        author=author,
        content_html=content_html,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_int(el: Tag | None) -> int:
    if not el:
        return 0
    text = el.get_text(strip=True)
    return _safe_int(text)


def _safe_int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        return 0
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/scraper/arca/test_parser_list.py -v
```

Expected: 4 passed

- [ ] **Step 6: 커밋**

```bash
git add app/scraper/arca/parser.py tests/scraper/arca/test_parser_list.py tests/scraper/arca/fixtures/
git commit -m "feat: rewrite parser with Pydantic models — article list, categories, pagination"
```

---

### Task 4: parser.py — 게시글 상세 파싱 테스트

**Files:**
- Create: `tests/scraper/arca/test_parser_detail.py`
- Create: `tests/scraper/arca/fixtures/article_detail.html`

- [ ] **Step 1: HTML fixture 저장**

```bash
uv run python -c "
from app.scraper.arca.client import ArcaClient
import os, pathlib

cookies = os.environ.get('ARCA_COOKIES', '')
c = ArcaClient(cookies)
resp = c.get('/b/aiart/168041856')
path = pathlib.Path('tests/scraper/arca/fixtures')
path.mkdir(parents=True, exist_ok=True)
(path / 'article_detail.html').write_text(resp.text, encoding='utf-8')
print(f'Saved {len(resp.text)} chars')
c.close()
"
```

- [ ] **Step 2: 테스트 작성**

`tests/scraper/arca/test_parser_detail.py`:

```python
from pathlib import Path

from app.scraper.arca.models import ArticleDetail, Attachment
from app.scraper.arca.parser import parse_article_detail

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_article_detail_meta():
    html = _load("article_detail.html")
    detail = parse_article_detail(html, article_id=168041856)
    assert detail.id == 168041856
    assert len(detail.title) > 0
    assert len(detail.author) > 0
    assert detail.view_count >= 0
    assert detail.vote_count >= 0
    assert detail.down_vote_count >= 0


def test_parse_article_detail_content():
    html = _load("article_detail.html")
    detail = parse_article_detail(html, article_id=168041856)
    assert len(detail.content_html) > 0


def test_parse_article_detail_attachments():
    html = _load("article_detail.html")
    detail = parse_article_detail(html, article_id=168041856)
    images = [a for a in detail.attachments if a.media_type == "image"]
    assert len(images) > 0
    for img in images:
        assert img.url.startswith("https://")


def test_parse_article_detail_excludes_emoticons():
    html = _load("article_detail.html")
    detail = parse_article_detail(html, article_id=168041856)
    for att in detail.attachments:
        assert "arca-emoticon" not in att.url
```

- [ ] **Step 3: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/scraper/arca/test_parser_detail.py -v
```

Expected: 4 passed (parser.py는 Task 3에서 이미 구현됨)

- [ ] **Step 4: 커밋**

```bash
git add tests/scraper/arca/test_parser_detail.py tests/scraper/arca/fixtures/article_detail.html
git commit -m "test: add article detail parser tests with fixture"
```

---

### Task 5: parser.py — 댓글 파싱 테스트

**Files:**
- Create: `tests/scraper/arca/test_parser_comments.py`
- Create: `tests/scraper/arca/fixtures/article_with_comments.html`

- [ ] **Step 1: HTML fixture 저장 — 댓글 + 대댓글 있는 글**

```bash
uv run python -c "
from app.scraper.arca.client import ArcaClient
import os, pathlib

cookies = os.environ.get('ARCA_COOKIES', '')
c = ArcaClient(cookies)
resp = c.get('/b/characterai/168046700')
path = pathlib.Path('tests/scraper/arca/fixtures')
path.mkdir(parents=True, exist_ok=True)
(path / 'article_with_comments.html').write_text(resp.text, encoding='utf-8')
print(f'Saved {len(resp.text)} chars')
c.close()
"
```

- [ ] **Step 2: 테스트 작성**

`tests/scraper/arca/test_parser_comments.py`:

```python
from pathlib import Path

from app.scraper.arca.models import Comment
from app.scraper.arca.parser import parse_comments

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_comments_returns_list():
    html = _load("article_with_comments.html")
    comments = parse_comments(html)
    assert len(comments) > 0
    assert all(isinstance(c, Comment) for c in comments)


def test_comment_has_fields():
    html = _load("article_with_comments.html")
    comments = parse_comments(html)
    c = comments[0]
    assert c.id.startswith("c_")
    assert len(c.author) > 0
    assert c.created_at.year > 2000


def test_comments_have_replies():
    html = _load("article_with_comments.html")
    comments = parse_comments(html)
    has_replies = any(len(c.replies) > 0 for c in comments)
    assert has_replies, "Expected at least one comment with replies"


def test_reply_structure():
    html = _load("article_with_comments.html")
    comments = parse_comments(html)
    for c in comments:
        for r in c.replies:
            assert r.id.startswith("c_")
            assert len(r.author) > 0
            assert r.replies == []  # 대댓글에 또 대댓글 중첩 없음
```

- [ ] **Step 3: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/scraper/arca/test_parser_comments.py -v
```

Expected: 4 passed

- [ ] **Step 4: 커밋**

```bash
git add tests/scraper/arca/test_parser_comments.py tests/scraper/arca/fixtures/article_with_comments.html
git commit -m "test: add comment parser tests with fixture"
```

---

### Task 6: ArcaChannel 구현

**Files:**
- Create: `app/scraper/arca/channel.py`
- Create: `tests/scraper/arca/test_channel.py`

- [ ] **Step 1: 테스트 작성**

`tests/scraper/arca/test_channel.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from app.scraper.arca.channel import ArcaChannel
from app.scraper.arca.models import ArticleDetail, ArticleList, Category, Comment

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _mock_client(fixture_name: str) -> MagicMock:
    client = MagicMock()
    resp = MagicMock()
    resp.text = _load(fixture_name)
    client.get.return_value = resp
    return client


def test_get_categories():
    client = _mock_client("article_list.html")
    channel = ArcaChannel(client, "characterai")
    cats = channel.get_categories()
    assert len(cats) > 0
    assert all(isinstance(c, Category) for c in cats)
    client.get.assert_called_once_with("/b/characterai", params={})


def test_get_articles_default():
    client = _mock_client("article_list.html")
    channel = ArcaChannel(client, "characterai")
    result = channel.get_articles()
    assert isinstance(result, ArticleList)
    assert len(result.articles) > 0
    assert result.current_page == 1
    client.get.assert_called_once_with("/b/characterai", params={"p": 1})


def test_get_articles_with_filters():
    client = _mock_client("article_list.html")
    channel = ArcaChannel(client, "characterai")
    channel.get_articles(category="일반", mode="best", sort="reg", cut=10, page=2)
    client.get.assert_called_once_with(
        "/b/characterai",
        params={"category": "일반", "mode": "best", "sort": "reg", "cut": 10, "p": 2},
    )


def test_search():
    client = _mock_client("article_list.html")
    channel = ArcaChannel(client, "characterai")
    result = channel.search(keyword="프롬", target="title", page=1)
    assert isinstance(result, ArticleList)
    client.get.assert_called_once_with(
        "/b/characterai",
        params={"target": "title", "keyword": "프롬", "p": 1},
    )


def test_get_article():
    client = _mock_client("article_detail.html")
    channel = ArcaChannel(client, "characterai")
    detail = channel.get_article(168041856)
    assert isinstance(detail, ArticleDetail)
    assert detail.id == 168041856
    client.get.assert_called_once_with("/b/characterai/168041856")


def test_get_comments():
    client = _mock_client("article_with_comments.html")
    channel = ArcaChannel(client, "characterai")
    comments = channel.get_comments(168046700)
    assert len(comments) > 0
    assert all(isinstance(c, Comment) for c in comments)
    client.get.assert_called_once_with("/b/characterai/168046700")
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
uv run pytest tests/scraper/arca/test_channel.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.scraper.arca.channel'`

- [ ] **Step 3: channel.py 구현**

`app/scraper/arca/channel.py`:

```python
from __future__ import annotations

from app.scraper.arca.models import ArticleDetail, ArticleList, Category, Comment
from app.scraper.arca.parser import (
    parse_article_detail,
    parse_article_list,
    parse_categories,
    parse_comments,
    parse_pagination,
)


class ArcaChannel:
    """arca.live 채널 단위 API."""

    def __init__(self, client, slug: str):
        self._client = client
        self._slug = slug

    @property
    def base_path(self) -> str:
        return f"/b/{self._slug}"

    def get_categories(self) -> list[Category]:
        resp = self._client.get(self.base_path, params={})
        return parse_categories(resp.text)

    def get_articles(
        self,
        *,
        category: str | None = None,
        mode: str | None = None,
        sort: str | None = None,
        cut: int | None = None,
        page: int = 1,
    ) -> ArticleList:
        params: dict = {}
        if category is not None:
            params["category"] = category
        if mode is not None:
            params["mode"] = mode
        if sort is not None:
            params["sort"] = sort
        if cut is not None:
            params["cut"] = cut
        params["p"] = page

        resp = self._client.get(self.base_path, params=params)
        articles = parse_article_list(resp.text)
        current_page, total_pages = parse_pagination(resp.text)
        return ArticleList(
            articles=articles,
            current_page=current_page,
            total_pages=total_pages,
        )

    def search(
        self,
        keyword: str,
        *,
        target: str = "all",
        page: int = 1,
    ) -> ArticleList:
        params: dict = {
            "target": target,
            "keyword": keyword,
            "p": page,
        }
        resp = self._client.get(self.base_path, params=params)
        articles = parse_article_list(resp.text)
        current_page, total_pages = parse_pagination(resp.text)
        return ArticleList(
            articles=articles,
            current_page=current_page,
            total_pages=total_pages,
        )

    def get_article(self, article_id: int) -> ArticleDetail:
        resp = self._client.get(f"{self.base_path}/{article_id}")
        return parse_article_detail(resp.text, article_id)

    def get_comments(self, article_id: int) -> list[Comment]:
        resp = self._client.get(f"{self.base_path}/{article_id}")
        return parse_comments(resp.text)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
uv run pytest tests/scraper/arca/test_channel.py -v
```

Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add app/scraper/arca/channel.py tests/scraper/arca/test_channel.py
git commit -m "feat: add ArcaChannel — channel-based API entry point"
```

---

### Task 7: __init__.py 공개 API + 통합 확인

**Files:**
- Modify: `app/scraper/arca/__init__.py`

- [ ] **Step 1: __init__.py에서 공개 API export**

`app/scraper/arca/__init__.py`:

```python
from app.scraper.arca.channel import ArcaChannel
from app.scraper.arca.client import ArcaClient
from app.scraper.arca.models import (
    ArticleDetail,
    ArticleList,
    ArticleRow,
    Attachment,
    Category,
    Comment,
)

__all__ = [
    "ArcaClient",
    "ArcaChannel",
    "ArticleDetail",
    "ArticleList",
    "ArticleRow",
    "Attachment",
    "Category",
    "Comment",
]
```

- [ ] **Step 2: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 통과 (18 tests)

- [ ] **Step 3: import 확인**

```bash
uv run python -c "
from app.scraper.arca import ArcaClient, ArcaChannel, ArticleList, Category
print('All imports OK')
"
```

- [ ] **Step 4: 커밋**

```bash
git add app/scraper/arca/__init__.py
git commit -m "feat: export public API from arca scraper package"
```
