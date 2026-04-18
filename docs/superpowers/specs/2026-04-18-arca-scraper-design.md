# Sentinel - arca.live 스크래퍼 설계

## 목적

arca.live 채널의 조회 기능을 프로그래밍 방식으로 사용할 수 있는 순수 Python 라이브러리.
서버 스크래핑 방식으로 동작하며, curl-cffi를 통해 Cloudflare를 우회한다.
나중에 FastAPI 라우터를 얇게 올려 웹 UI에서 사용할 수 있지만, 스크래퍼 자체는 API에 의존하지 않는다.

## 파일 구조

```
app/scraper/arca/
├── __init__.py
├── client.py      # ArcaClient - curl-cffi HTTP 클라이언트 (CF 우회, 쿠키 관리)
├── channel.py     # ArcaChannel - 채널 중심 API 진입점
├── models.py      # Pydantic 모델
└── parser.py      # HTML → 모델 변환 파서
```

## 쿠키 관리

`.env` 파일에 `ARCA_COOKIES` 환경변수로 저장. `python-dotenv`로 로드.

```env
ARCA_COOKIES="arca.nick=...; arca.at=...; ..."
```

`ArcaClient()`를 인자 없이 호출하면 `.env`에서 자동 로드.
명시적으로 `ArcaClient(cookies="...")` 전달도 가능.

## API 설계

### ArcaClient (client.py)

HTTP 통신 담당. curl-cffi의 `requests.Session`을 감싸며 `impersonate="chrome136"`으로 CF TLS 핑거프린트 우회.

```python
client = ArcaClient()              # .env에서 쿠키 자동 로드
client = ArcaClient(cookies="...") # 직접 전달
resp = client.get("/b/characterai")
client.close()
```

### ArcaChannel (channel.py)

채널 slug 기반 진입점. 모든 조회 기능을 메서드로 제공.

```python
channel = ArcaChannel(client, "characterai")
```

#### 채널 카테고리 목록

```python
channel.get_categories() -> list[Category]
```

채널 페이지에서 `.board-category a` 요소를 파싱하여 카테고리 탭 목록 반환.

#### 게시글 목록

```python
channel.get_articles(
    category: str | None = None,   # "일반", "질문", "감정봇" 등
    mode: str | None = None,       # None | "best" (개념글)
    sort: str | None = None,       # None | "reg" (등록순)
    cut: int | None = None,        # None | 10, 20 등 (추천컷)
    page: int = 1,
) -> ArticleList
```

URL 조합: `/b/{slug}?category={category}&mode={mode}&sort={sort}&cut={cut}&p={page}`
None인 파라미터는 쿼리에서 제외.
공지(`.notice` 클래스)는 제외하고 일반 글만 반환.

#### 검색

```python
channel.search(
    keyword: str,
    target: str = "all",           # all | title_content | title | content | nickname | comment
    page: int = 1,
) -> ArticleList
```

URL: `/b/{slug}?target={target}&keyword={keyword}&p={page}`

#### 게시글 상세

```python
channel.get_article(article_id: int) -> ArticleDetail
```

URL: `/b/{slug}/{article_id}`
`.article-head`에서 메타 정보, `.article-content`에서 본문 HTML과 첨부파일(이미지/영상) URL 추출.

#### 댓글 조회

```python
channel.get_comments(article_id: int) -> list[Comment]
```

게시글 상세 페이지에서 `.comment-wrapper` > `.comment-item`을 파싱.
댓글은 전부 한 번에 로드됨 (서버 측 페이지네이션 없음).
대댓글은 같은 `.comment-wrapper` 내 두 번째 이후 `.comment-item`으로 구분, `Comment.replies`에 중첩.

## 데이터 모델 (Pydantic)

### Category

```python
class Category(BaseModel):
    name: str           # "일반", "질문", "에셋·모듈봇" 등
    slug: str           # URL 인코딩된 카테고리 값 (쿼리 파라미터용)
```

### ArticleRow

게시글 목록의 한 행.

```python
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
```

### ArticleList

게시글 목록 + 페이지네이션 정보.

```python
class ArticleList(BaseModel):
    articles: list[ArticleRow]
    current_page: int
    total_pages: int
```

### Attachment

본문 내 첨부 미디어.

```python
class Attachment(BaseModel):
    url: str                        # 원본 src URL 그대로
    media_type: str                 # "image" | "video"
```

### ArticleDetail

게시글 상세 정보.

```python
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
    content_html: str               # .article-content 내부 HTML 원본
    attachments: list[Attachment]    # 본문 내 이미지/영상 URL
```

### Comment

댓글. 대댓글은 replies로 중첩.

```python
class Comment(BaseModel):
    id: str                         # "c_884519773" 형태
    author: str
    content_html: str               # .message 내부 HTML
    created_at: datetime
    replies: list[Comment] = []
```

## HTML 파싱 규칙 (parser.py)

### 게시글 목록

- 선택자: `.list-table a.vrow.column`
- 공지 제외: `notice` 클래스 포함 시 스킵
- 헤더 제외: `head` 클래스 포함 시 스킵
- 필드 매핑:
  - `.col-id` → id (int)
  - `.col-title .title` → title (텍스트)
  - `.col-title .badge` → category
  - `.col-title .comment-count` → comment_count (숫자 추출)
  - `.col-author` → author
  - `.col-time time[datetime]` → created_at
  - `.col-view` → view_count
  - `.col-rate` → vote_count
  - `.media-icon.ion-ios-photos-outline` 존재 → has_image
  - `.media-icon.ion-ios-videocam-outline` 존재 → has_video

### 페이지네이션

- 선택자: `.pagination-wrapper .pagination a`
- 마지막 숫자 페이지 링크에서 total_pages 추출

### 카테고리 탭

- 선택자: `.board-category a`
- href에서 `category=` 쿼리 파라미터 값 추출 → slug
- 텍스트 → name

### 게시글 상세

- `.article-head .title` → title (카테고리 뱃지 텍스트 제외한 순수 제목)
- `.article-head .article-info .head` + `.body` 쌍 → 추천/비추천/댓글/조회수/작성일
- `.article-head .user-info` → author
- `.article-body .article-content` → content_html (innerHTML)
- `.article-content img` → Attachment(media_type="image"), src URL 그대로
- `.article-content video` → Attachment(media_type="video")

### 댓글

- `.comment-wrapper` 단위로 그룹핑
- 각 wrapper 내 첫 `.comment-item` → 부모 댓글
- 이후 `.comment-item` → replies
- `.comment-item`의 id 속성 → Comment.id
- `.user-info` → author
- `.message` → content_html
- `time[datetime]` → created_at

## 이미지 처리

img src URL을 그대로 사용. arca.live가 서빙하는 포맷(png/webp 등)이 곧 원본.
별도 확장자 변환이나 URL 조작 없음.

## URL 패턴 정리

| 기능 | URL |
|------|-----|
| 전체글 | `/b/{slug}` |
| 카테고리 | `/b/{slug}?category={category}` |
| 개념글 | `/b/{slug}?mode=best` |
| 등록순 | `/b/{slug}?sort=reg` |
| 추천컷 | `/b/{slug}?cut={n}` |
| 페이지 | `/b/{slug}?p={page}` |
| 검색 | `/b/{slug}?target={target}&keyword={keyword}` |
| 상세 | `/b/{slug}/{article_id}` |
| 복합 | 쿼리 파라미터 조합 가능 (예: `?category=일반&mode=best&p=2`) |
