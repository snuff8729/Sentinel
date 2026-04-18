# 웹 UI 설계

## 목적

arca.live 게시글 브라우징, 상세 조회, 백업 큐 관리를 웹 인터페이스로 제공한다.
FastAPI 서버 하나에서 API + 프론트엔드 정적 파일을 모두 서빙한다.

## 기술 스택

- Vite + React + TypeScript
- shadcn/ui + Tailwind CSS
- 빌드 결과물(`web/dist/`)은 FastAPI에서 정적 파일로 서빙
- 개발 시 Vite dev server(포트 5173) → FastAPI(포트 8000) 프록시

## 프로젝트 구조

```
sentinel/
  app/                # Python 백엔드 (기존)
  web/                # React 프론트엔드
    src/
      pages/
        ChannelPage.tsx        # 채널 입력 + 게시글 목록
        ArticleDetailPage.tsx  # 게시글 상세 (본문 + 댓글)
        QueuePage.tsx          # 다운로드 큐 상태/제어
        HistoryPage.tsx        # 백업 이력
      components/
        Layout.tsx             # 공통 레이아웃 (사이드바/네비게이션)
        ArticleList.tsx        # 게시글 테이블 (선택, 필터, 페이지네이션)
        QueuePanel.tsx         # 큐 진행도 + 일시정지/재개/취소
        CommentList.tsx        # 댓글 목록 (대댓글 중첩)
      hooks/
        useSSE.ts              # EventSource 커스텀 훅
      api/
        client.ts              # fetch 래퍼 + API 함수
        types.ts               # TypeScript 타입 정의 (백엔드 모델 미러링)
      App.tsx
      main.tsx
    vite.config.ts
    tailwind.config.ts
    tsconfig.json
    package.json
```

## 페이지 구성

### 1. 채널 페이지 (`/channel/:slug`)

채널 URL 또는 slug를 입력하면 해당 채널의 게시글 목록을 표시한다.

- 채널 URL 입력 바 (예: `https://arca.live/b/characterai` 입력 → slug 추출 → 이동)
- 카테고리 탭 (API: `GET /api/channel/{slug}/categories`)
- 필터: 개념글(`mode=best`), 등록순(`sort=reg`), 추천컷(`cut=N`)
- 검색: 키워드 + 검색 대상(전체/제목/내용/닉네임/댓글)
- 게시글 목록 테이블
  - 컬럼: 체크박스, 번호, 제목, 카테고리, 작성자, 작성일, 조회수, 추천, 댓글수
  - 제목 클릭 → 게시글 상세 페이지로 이동
  - 체크박스 선택 → "백업 큐에 추가" 버튼 활성화
- 페이지네이션

### 2. 게시글 상세 (`/article/:slug/:id`)

스크래퍼 API로 게시글 상세를 가져와서 React 컴포넌트로 렌더링한다.

- 헤더: 제목, 카테고리, 작성자, 작성일, 조회수, 추천/비추천
- 본문: `content_html`을 `dangerouslySetInnerHTML`로 렌더링
- 첨부 미디어: 이미지/비디오 표시
- 댓글 목록: 대댓글 중첩 표시
- "이 글 백업" 버튼

### 3. 다운로드 큐 (`/queue`)

SSE로 실시간 상태를 표시하고 제어 버튼을 제공한다.

- 현재 처리 중인 게시글: 제목 + 파일 진행도 바 (예: 15/73, 20.5%)
- 대기 목록: 순서대로 표시
- 제어 버튼: 일시정지/재개, 개별 취소
- SSE 이벤트로 실시간 업데이트 (useSSE 훅)

### 4. 백업 이력 (`/history`)

완료/실패/취소된 백업 기록을 조회한다.

- 목록: 게시글 제목, 채널, 상태, 백업 시각, 에러 메시지
- 상태별 필터 (completed/failed/cancelled)
- 실패한 게시글: 에러 내용 표시 + 재시도 버튼

## 필요한 백엔드 API 추가

기존 스크래퍼를 REST API로 노출하는 엔드포인트. `app/api/channel.py`에 구현.

```
GET  /api/channel/{slug}/categories
     → list[Category]

GET  /api/channel/{slug}/articles?category=&mode=&sort=&cut=&page=1
     → ArticleList

GET  /api/channel/{slug}/search?keyword=&target=all&page=1
     → ArticleList

GET  /api/article/{slug}/{id}
     → ArticleDetail

GET  /api/article/{slug}/{id}/comments
     → list[Comment]
```

백업 이력 조회 엔드포인트. `app/api/backup.py`에 추가.

```
GET  /api/backup/history?status=completed&page=1
     → { articles: list[Article], total: int, page: int }
```

## FastAPI 정적 파일 서빙

`app/main.py`에서 빌드된 React 결과물을 서빙한다.
API 라우트(`/api/`)를 먼저 등록하고, 나머지 모든 경로는 React의 `index.html`로 폴백한다.

```python
from fastapi.staticfiles import StaticFiles

# API 라우터 등록 (먼저)
app.include_router(channel_router, prefix="/api/channel")
app.include_router(backup_router, prefix="/api/backup")

# React 빌드 결과물 서빙 (나중에)
app.mount("/", StaticFiles(directory="web/dist", html=True))
```

## Vite 개발 프록시

개발 시 Vite dev server에서 `/api/` 요청을 FastAPI로 프록시한다.

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

## TypeScript 타입 정의

백엔드 Pydantic/SQLModel 모델을 미러링한다. `web/src/api/types.ts`에 정의.

```typescript
interface Category {
  name: string
  slug: string
}

interface ArticleRow {
  id: number
  title: string
  category: string | null
  comment_count: number
  author: string
  created_at: string
  view_count: number
  vote_count: number
  has_image: boolean
  has_video: boolean
  url: string
}

interface ArticleList {
  articles: ArticleRow[]
  current_page: number
  total_pages: number
}

interface Attachment {
  url: string
  media_type: string
}

interface ArticleDetail {
  id: number
  title: string
  category: string | null
  author: string
  created_at: string
  view_count: number
  vote_count: number
  down_vote_count: number
  comment_count: number
  content_html: string
  attachments: Attachment[]
}

interface Comment {
  id: string
  author: string
  content_html: string
  created_at: string
  replies: Comment[]
}

// SSE 이벤트
interface QueueStatus {
  paused: boolean
  current: { article_id: number; channel_slug: string } | null
  pending: { article_id: number; channel_slug: string }[]
}

interface FileCompletedEvent {
  article_id: number
  filename: string
  size_kb: number
  current: number
  total: number
  file_type: string
}

interface ArticleCompletedEvent {
  article_id: number
  success_count: number
  fail_count: number
}
```

## SSE 연동

`useSSE` 커스텀 훅으로 EventSource를 관리한다.

```typescript
// hooks/useSSE.ts
function useSSE(url: string, handlers: Record<string, (data: any) => void>) {
  useEffect(() => {
    const source = new EventSource(url)
    for (const [event, handler] of Object.entries(handlers)) {
      source.addEventListener(event, (e) => handler(JSON.parse(e.data)))
    }
    return () => source.close()
  }, [url])
}
```

QueuePage에서 사용:

```typescript
useSSE('/api/backup/events', {
  queue_updated: (data) => setQueue(data.queue),
  article_started: (data) => setCurrent(data),
  file_completed: (data) => setProgress(data),
  article_completed: (data) => handleComplete(data),
  worker_paused: () => setPaused(true),
  worker_resumed: () => setPaused(false),
})
```

## 범위

### MVP에 포함
- 채널 페이지 (목록, 필터, 검색, 페이지네이션)
- 게시글 상세 페이지 (본문 + 댓글)
- 다운로드 큐 페이지 (SSE 실시간 + 제어)
- 백업 이력 페이지
- 채널/게시글 API 엔드포인트 추가
- FastAPI 정적 파일 서빙

### MVP에 미포함
- 다크 모드
- 반응형 모바일 레이아웃
- 사용자 인증
- 설정 페이지 (딜레이 등 런타임 변경)
