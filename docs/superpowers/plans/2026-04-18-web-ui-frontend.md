# 웹 UI 프론트엔드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** React + TypeScript로 채널 브라우징, 게시글 상세, 다운로드 큐, 백업 이력 페이지를 구현한다.

**Architecture:** Vite + React + TypeScript + shadcn/ui + Tailwind CSS. Vite dev server에서 `/api/` 요청은 FastAPI(8000)로 프록시. 빌드 결과물은 `web/dist/`에 출력되어 FastAPI가 정적 서빙.

**Tech Stack:** Vite, React 19, TypeScript, shadcn/ui, Tailwind CSS, React Router

**Spec:** `docs/superpowers/specs/2026-04-18-web-ui-design.md`

---

### Task 1: React 프로젝트 스캐폴딩

**Files:**
- Create: `web/` 디렉토리 전체 (Vite 프로젝트)

- [ ] **Step 1: Vite 프로젝트 생성**

```bash
cd /Users/user/project/snuff/sentinel
npm create vite@latest web -- --template react-ts
```

- [ ] **Step 2: 의존성 설치**

```bash
cd web
npm install
npm install react-router-dom
npm install -D tailwindcss @tailwindcss/vite
```

- [ ] **Step 3: Tailwind CSS 설정**

`web/src/index.css`를 다음으로 교체:

```css
@import "tailwindcss";
```

`web/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

- [ ] **Step 4: shadcn/ui 설치**

```bash
cd web
npx shadcn@latest init -d
```

필요한 컴포넌트 추가:

```bash
npx shadcn@latest add button table badge input select tabs card
```

- [ ] **Step 5: 기본 App.tsx 설정**

`web/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background">
        <nav className="border-b px-6 py-3 flex gap-4">
          <Link to="/" className="font-bold text-lg">Sentinel</Link>
          <Link to="/queue" className="text-muted-foreground hover:text-foreground">큐</Link>
          <Link to="/history" className="text-muted-foreground hover:text-foreground">이력</Link>
        </nav>
        <main className="p-6">
          <Routes>
            <Route path="/" element={<div>채널 URL을 입력하세요</div>} />
            <Route path="/channel/:slug" element={<div>채널 페이지</div>} />
            <Route path="/article/:slug/:id" element={<div>게시글 상세</div>} />
            <Route path="/queue" element={<div>다운로드 큐</div>} />
            <Route path="/history" element={<div>백업 이력</div>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
```

`web/src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 6: 개발 서버 확인**

```bash
cd web && npm run dev
```

브라우저에서 `http://localhost:5173` 접속하여 네비게이션이 보이는지 확인.

- [ ] **Step 7: 불필요한 파일 정리 + 커밋**

```bash
rm -f web/src/App.css web/src/assets/react.svg web/public/vite.svg
cd /Users/user/project/snuff/sentinel
echo "web/node_modules/" >> .gitignore
git add web/ .gitignore
git commit -m "feat: scaffold React + TypeScript + shadcn/ui frontend"
```

---

### Task 2: API 클라이언트 + TypeScript 타입

**Files:**
- Create: `web/src/api/types.ts`
- Create: `web/src/api/client.ts`

- [ ] **Step 1: 타입 정의**

`web/src/api/types.ts`:

```typescript
export interface Category {
  name: string
  slug: string
}

export interface ArticleRow {
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

export interface ArticleList {
  articles: ArticleRow[]
  current_page: number
  total_pages: number
}

export interface Attachment {
  url: string
  media_type: string
}

export interface ArticleDetail {
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

export interface Comment {
  id: string
  author: string
  content_html: string
  created_at: string
  replies: Comment[]
}

export interface QueueStatus {
  paused: boolean
  current: { article_id: number; channel_slug: string } | null
  pending: { article_id: number; channel_slug: string }[]
}

export interface BackupHistoryItem {
  id: number
  channel_slug: string
  title: string
  author: string
  category: string | null
  backup_status: string
  backup_error: string | null
  backed_up_at: string | null
}

export interface SSEFileCompleted {
  article_id: number
  filename: string
  size_kb: number
  current: number
  total: number
  file_type: string
}

export interface SSEArticleStarted {
  article_id: number
  title: string
  total_files: number
}

export interface SSEArticleCompleted {
  article_id: number
  success_count: number
  fail_count: number
}
```

- [ ] **Step 2: API 클라이언트**

`web/src/api/client.ts`:

```typescript
import type {
  ArticleDetail,
  ArticleList,
  BackupHistoryItem,
  Category,
  Comment,
  QueueStatus,
} from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

// Channel API
export const channelApi = {
  getCategories: (slug: string) =>
    get<Category[]>(`/channel/${slug}/categories`),

  getArticles: (slug: string, params?: {
    category?: string
    mode?: string
    sort?: string
    cut?: number
    page?: number
  }) => {
    const searchParams = new URLSearchParams()
    if (params?.category) searchParams.set('category', params.category)
    if (params?.mode) searchParams.set('mode', params.mode)
    if (params?.sort) searchParams.set('sort', params.sort)
    if (params?.cut) searchParams.set('cut', String(params.cut))
    if (params?.page) searchParams.set('page', String(params.page))
    const qs = searchParams.toString()
    return get<ArticleList>(`/channel/${slug}/articles${qs ? `?${qs}` : ''}`)
  },

  search: (slug: string, keyword: string, target = 'all', page = 1) =>
    get<ArticleList>(`/channel/${slug}/search?keyword=${encodeURIComponent(keyword)}&target=${target}&page=${page}`),
}

// Article API
export const articleApi = {
  getDetail: (slug: string, id: number) =>
    get<ArticleDetail>(`/article/${slug}/${id}`),

  getComments: (slug: string, id: number) =>
    get<Comment[]>(`/article/${slug}/${id}/comments`),
}

// Backup API
export const backupApi = {
  enqueue: (slug: string, articleId: number, force = false) =>
    post<{ status: string; position: number }>(`/backup/${slug}/${articleId}${force ? '?force=true' : ''}`),

  cancel: (articleId: number) =>
    del<{ status: string }>(`/backup/${articleId}`),

  pause: () => post<{ status: string }>('/backup/pause'),
  resume: () => post<{ status: string }>('/backup/resume'),

  getQueue: () => get<QueueStatus>('/backup/queue'),

  getHistory: (status?: string) =>
    get<BackupHistoryItem[]>(`/backup/history${status ? `?status=${status}` : ''}`),
}
```

- [ ] **Step 3: 커밋**

```bash
cd /Users/user/project/snuff/sentinel
git add web/src/api/
git commit -m "feat: add TypeScript API types and client"
```

---

### Task 3: useSSE 훅

**Files:**
- Create: `web/src/hooks/useSSE.ts`

- [ ] **Step 1: useSSE 훅 구현**

`web/src/hooks/useSSE.ts`:

```typescript
import { useEffect, useRef } from 'react'

type EventHandlers = Record<string, (data: unknown) => void>

export function useSSE(url: string, handlers: EventHandlers) {
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  useEffect(() => {
    const source = new EventSource(url)

    const listeners: [string, (e: MessageEvent) => void][] = []
    for (const eventType of Object.keys(handlersRef.current)) {
      const listener = (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          handlersRef.current[eventType]?.(data)
        } catch {
          // ignore parse errors
        }
      }
      source.addEventListener(eventType, listener)
      listeners.push([eventType, listener])
    }

    return () => {
      for (const [type, listener] of listeners) {
        source.removeEventListener(type, listener)
      }
      source.close()
    }
  }, [url])
}
```

- [ ] **Step 2: 커밋**

```bash
cd /Users/user/project/snuff/sentinel
git add web/src/hooks/
git commit -m "feat: add useSSE hook for real-time event streaming"
```

---

### Task 4: 채널 페이지 — 게시글 목록

**Files:**
- Create: `web/src/pages/ChannelPage.tsx`
- Create: `web/src/components/ArticleList.tsx`
- Create: `web/src/components/ChannelInput.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 채널 입력 컴포넌트**

`web/src/components/ChannelInput.tsx`:

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export function ChannelInput() {
  const [url, setUrl] = useState('')
  const navigate = useNavigate()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // https://arca.live/b/characterai → characterai
    const match = url.match(/arca\.live\/b\/([^/?]+)/)
    const slug = match ? match[1] : url.trim()
    if (slug) navigate(`/channel/${slug}`)
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 max-w-xl">
      <Input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="채널 URL 또는 slug 입력 (예: characterai)"
        className="flex-1"
      />
      <Button type="submit">이동</Button>
    </form>
  )
}
```

- [ ] **Step 2: 게시글 목록 컴포넌트**

`web/src/components/ArticleList.tsx`:

```tsx
import { Link } from 'react-router-dom'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import type { ArticleRow } from '@/api/types'

interface Props {
  slug: string
  articles: ArticleRow[]
  selected: Set<number>
  onToggle: (id: number) => void
  onToggleAll: () => void
}

export function ArticleList({ slug, articles, selected, onToggle, onToggleAll }: Props) {
  const allSelected = articles.length > 0 && articles.every(a => selected.has(a.id))

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10">
            <Checkbox checked={allSelected} onCheckedChange={onToggleAll} />
          </TableHead>
          <TableHead className="w-20">번호</TableHead>
          <TableHead>제목</TableHead>
          <TableHead className="w-24">작성자</TableHead>
          <TableHead className="w-28">작성일</TableHead>
          <TableHead className="w-16 text-right">조회</TableHead>
          <TableHead className="w-16 text-right">추천</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {articles.map((article) => (
          <TableRow key={article.id}>
            <TableCell>
              <Checkbox
                checked={selected.has(article.id)}
                onCheckedChange={() => onToggle(article.id)}
              />
            </TableCell>
            <TableCell className="text-muted-foreground">{article.id}</TableCell>
            <TableCell>
              <Link
                to={`/article/${slug}/${article.id}`}
                className="hover:underline"
              >
                {article.category && (
                  <Badge variant="secondary" className="mr-1.5 text-xs">
                    {article.category}
                  </Badge>
                )}
                {article.title}
                {article.comment_count > 0 && (
                  <span className="text-muted-foreground ml-1">[{article.comment_count}]</span>
                )}
              </Link>
            </TableCell>
            <TableCell className="text-sm">{article.author}</TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {new Date(article.created_at).toLocaleDateString('ko-KR')}
            </TableCell>
            <TableCell className="text-right text-sm">{article.view_count}</TableCell>
            <TableCell className="text-right text-sm">{article.vote_count}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

shadcn checkbox 추가가 필요할 수 있음:

```bash
cd web && npx shadcn@latest add checkbox
```

- [ ] **Step 3: 채널 페이지**

`web/src/pages/ChannelPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ArticleList } from '@/components/ArticleList'
import { channelApi, backupApi } from '@/api/client'
import type { ArticleList as ArticleListType, Category } from '@/api/types'

export function ChannelPage() {
  const { slug } = useParams<{ slug: string }>()
  const [searchParams, setSearchParams] = useSearchParams()

  const [categories, setCategories] = useState<Category[]>([])
  const [data, setData] = useState<ArticleListType | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)

  const category = searchParams.get('category') || undefined
  const mode = searchParams.get('mode') || undefined
  const page = Number(searchParams.get('page') || '1')

  useEffect(() => {
    if (!slug) return
    channelApi.getCategories(slug).then(setCategories)
  }, [slug])

  useEffect(() => {
    if (!slug) return
    setLoading(true)
    setSelected(new Set())
    channelApi.getArticles(slug, { category, mode, page })
      .then(setData)
      .finally(() => setLoading(false))
  }, [slug, category, mode, page])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!slug || !keyword.trim()) return
    setLoading(true)
    channelApi.search(slug, keyword)
      .then(setData)
      .finally(() => setLoading(false))
  }

  const updateParams = (updates: Record<string, string | undefined>) => {
    const params = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(updates)) {
      if (v) params.set(k, v)
      else params.delete(k)
    }
    params.delete('page') // reset page on filter change
    setSearchParams(params)
  }

  const handleToggle = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleToggleAll = () => {
    if (!data) return
    const allSelected = data.articles.every(a => selected.has(a.id))
    if (allSelected) {
      setSelected(new Set())
    } else {
      setSelected(new Set(data.articles.map(a => a.id)))
    }
  }

  const handleBackup = async () => {
    if (!slug) return
    for (const id of selected) {
      await backupApi.enqueue(slug, id)
    }
    setSelected(new Set())
    alert(`${selected.size}개 게시글을 백업 큐에 추가했습니다.`)
  }

  const setPage = (p: number) => {
    const params = new URLSearchParams(searchParams)
    params.set('page', String(p))
    setSearchParams(params)
  }

  if (!slug) return null

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">/b/{slug}</h1>

      {/* 카테고리 탭 */}
      <div className="flex flex-wrap gap-1">
        <Button
          variant={!category ? 'default' : 'ghost'}
          size="sm"
          onClick={() => updateParams({ category: undefined })}
        >
          전체
        </Button>
        {categories.map(c => (
          <Button
            key={c.slug}
            variant={category === c.slug ? 'default' : 'ghost'}
            size="sm"
            onClick={() => updateParams({ category: c.slug || undefined })}
          >
            {c.name}
          </Button>
        ))}
      </div>

      {/* 필터 + 검색 */}
      <div className="flex gap-2 items-center">
        <Button
          variant={mode === 'best' ? 'default' : 'outline'}
          size="sm"
          onClick={() => updateParams({ mode: mode === 'best' ? undefined : 'best' })}
        >
          개념글
        </Button>
        <div className="flex-1" />
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="검색..."
            className="w-48"
          />
          <Button type="submit" size="sm" variant="outline">검색</Button>
        </form>
      </div>

      {/* 선택 액션 */}
      {selected.size > 0 && (
        <div className="flex items-center gap-2 p-2 bg-muted rounded">
          <span className="text-sm">{selected.size}개 선택</span>
          <Button size="sm" onClick={handleBackup}>백업 큐에 추가</Button>
        </div>
      )}

      {/* 게시글 목록 */}
      {loading ? (
        <div className="text-center py-8 text-muted-foreground">로딩 중...</div>
      ) : data ? (
        <>
          <ArticleList
            slug={slug}
            articles={data.articles}
            selected={selected}
            onToggle={handleToggle}
            onToggleAll={handleToggleAll}
          />

          {/* 페이지네이션 */}
          <div className="flex justify-center gap-1">
            {Array.from({ length: data.total_pages }, (_, i) => i + 1).map(p => (
              <Button
                key={p}
                variant={p === data.current_page ? 'default' : 'outline'}
                size="sm"
                onClick={() => setPage(p)}
              >
                {p}
              </Button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  )
}
```

- [ ] **Step 4: App.tsx 업데이트**

`web/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { ChannelInput } from '@/components/ChannelInput'
import { ChannelPage } from '@/pages/ChannelPage'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background">
        <nav className="border-b px-6 py-3 flex items-center gap-4">
          <Link to="/" className="font-bold text-lg">Sentinel</Link>
          <Link to="/queue" className="text-muted-foreground hover:text-foreground">큐</Link>
          <Link to="/history" className="text-muted-foreground hover:text-foreground">이력</Link>
        </nav>
        <main className="p-6">
          <Routes>
            <Route path="/" element={
              <div className="space-y-6">
                <h1 className="text-2xl font-bold">채널 입력</h1>
                <ChannelInput />
              </div>
            } />
            <Route path="/channel/:slug" element={<ChannelPage />} />
            <Route path="/article/:slug/:id" element={<div>게시글 상세 (TODO)</div>} />
            <Route path="/queue" element={<div>다운로드 큐 (TODO)</div>} />
            <Route path="/history" element={<div>백업 이력 (TODO)</div>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
```

- [ ] **Step 5: 개발 서버 확인**

FastAPI 서버가 8000에서 실행 중인 상태에서:

```bash
cd web && npm run dev
```

`http://localhost:5173`에서 채널 URL 입력 → 게시글 목록이 보이는지 확인.

- [ ] **Step 6: 커밋**

```bash
cd /Users/user/project/snuff/sentinel
git add web/src/
git commit -m "feat: add channel page with article list, filters, pagination"
```

---

### Task 5: 게시글 상세 페이지

**Files:**
- Create: `web/src/pages/ArticleDetailPage.tsx`
- Create: `web/src/components/CommentList.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 댓글 목록 컴포넌트**

`web/src/components/CommentList.tsx`:

```tsx
import type { Comment } from '@/api/types'

function CommentItem({ comment, isReply = false }: { comment: Comment; isReply?: boolean }) {
  return (
    <div className={`py-3 ${isReply ? 'ml-8 border-l-2 pl-4' : 'border-b'}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="font-medium text-sm">{comment.author}</span>
        <span className="text-xs text-muted-foreground">
          {new Date(comment.created_at).toLocaleString('ko-KR')}
        </span>
      </div>
      <div
        className="text-sm prose prose-sm max-w-none"
        dangerouslySetInnerHTML={{ __html: comment.content_html }}
      />
      {comment.replies.map(reply => (
        <CommentItem key={reply.id} comment={reply} isReply />
      ))}
    </div>
  )
}

export function CommentList({ comments }: { comments: Comment[] }) {
  return (
    <div>
      <h3 className="font-bold mb-2">댓글 ({comments.length})</h3>
      {comments.map(c => (
        <CommentItem key={c.id} comment={c} />
      ))}
    </div>
  )
}
```

- [ ] **Step 2: 게시글 상세 페이지**

`web/src/pages/ArticleDetailPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CommentList } from '@/components/CommentList'
import { articleApi, backupApi } from '@/api/client'
import type { ArticleDetail, Comment } from '@/api/types'

export function ArticleDetailPage() {
  const { slug, id } = useParams<{ slug: string; id: string }>()
  const [detail, setDetail] = useState<ArticleDetail | null>(null)
  const [comments, setComments] = useState<Comment[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!slug || !id) return
    const articleId = Number(id)
    setLoading(true)
    Promise.all([
      articleApi.getDetail(slug, articleId),
      articleApi.getComments(slug, articleId),
    ]).then(([d, c]) => {
      setDetail(d)
      setComments(c)
    }).finally(() => setLoading(false))
  }, [slug, id])

  const handleBackup = async () => {
    if (!slug || !id) return
    await backupApi.enqueue(slug, Number(id))
    alert('백업 큐에 추가했습니다.')
  }

  if (loading) return <div className="text-center py-8 text-muted-foreground">로딩 중...</div>
  if (!detail) return <div className="text-center py-8">게시글을 찾을 수 없습니다.</div>

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* 헤더 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          {detail.category && <Badge variant="secondary">{detail.category}</Badge>}
          <h1 className="text-2xl font-bold">{detail.title}</h1>
        </div>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{detail.author}</span>
          <span>{new Date(detail.created_at).toLocaleString('ko-KR')}</span>
          <span>조회 {detail.view_count}</span>
          <span>추천 {detail.vote_count}</span>
          <span>비추 {detail.down_vote_count}</span>
        </div>
      </div>

      {/* 백업 버튼 */}
      <Button onClick={handleBackup}>이 글 백업</Button>

      {/* 본문 */}
      <div
        className="prose prose-sm max-w-none border-t pt-4"
        dangerouslySetInnerHTML={{ __html: detail.content_html }}
      />

      {/* 댓글 */}
      <div className="border-t pt-4">
        <CommentList comments={comments} />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: App.tsx 업데이트**

`web/src/App.tsx` — ArticleDetailPage import 추가 및 라우트 교체:

```tsx
import { ArticleDetailPage } from '@/pages/ArticleDetailPage'

// Routes 내:
<Route path="/article/:slug/:id" element={<ArticleDetailPage />} />
```

- [ ] **Step 4: 개발 서버 확인**

채널 페이지에서 게시글 제목 클릭 → 상세 페이지가 본문 + 댓글과 함께 표시되는지 확인.

- [ ] **Step 5: 커밋**

```bash
cd /Users/user/project/snuff/sentinel
git add web/src/
git commit -m "feat: add article detail page with comments"
```

---

### Task 6: 다운로드 큐 페이지

**Files:**
- Create: `web/src/pages/QueuePage.tsx`
- Create: `web/src/components/QueuePanel.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 큐 패널 컴포넌트**

`web/src/components/QueuePanel.tsx`:

```tsx
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface QueueItem {
  article_id: number
  channel_slug: string
  title?: string
}

interface CurrentProgress {
  article_id: number
  title: string
  current: number
  total: number
}

interface Props {
  paused: boolean
  current: CurrentProgress | null
  pending: QueueItem[]
  onPause: () => void
  onResume: () => void
  onCancel: (articleId: number) => void
}

export function QueuePanel({ paused, current, pending, onPause, onResume, onCancel }: Props) {
  return (
    <div className="space-y-4">
      {/* 제어 버튼 */}
      <div className="flex gap-2">
        {paused ? (
          <Button onClick={onResume}>재개</Button>
        ) : (
          <Button variant="outline" onClick={onPause}>일시정지</Button>
        )}
      </div>

      {/* 현재 처리 중 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">처리 중</CardTitle>
        </CardHeader>
        <CardContent>
          {current ? (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium">{current.title}</span>
                <span className="text-muted-foreground">{current.current}/{current.total}</span>
              </div>
              <div className="w-full bg-secondary rounded-full h-2">
                <div
                  className="bg-primary rounded-full h-2 transition-all"
                  style={{ width: `${current.total > 0 ? (current.current / current.total) * 100 : 0}%` }}
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {paused ? '일시정지됨' : '대기 중인 작업 없음'}
            </p>
          )}
        </CardContent>
      </Card>

      {/* 대기 목록 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">대기 ({pending.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {pending.length === 0 ? (
            <p className="text-sm text-muted-foreground">대기 중인 작업 없음</p>
          ) : (
            <div className="space-y-2">
              {pending.map((item, i) => (
                <div key={item.article_id} className="flex justify-between items-center py-1">
                  <span className="text-sm">
                    {i + 1}. [{item.channel_slug}] #{item.article_id}
                    {item.title && ` — ${item.title}`}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onCancel(item.article_id)}
                  >
                    취소
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: 큐 페이지**

`web/src/pages/QueuePage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { QueuePanel } from '@/components/QueuePanel'
import { backupApi } from '@/api/client'
import { useSSE } from '@/hooks/useSSE'
import type { SSEArticleStarted, SSEFileCompleted, SSEArticleCompleted } from '@/api/types'

interface CurrentProgress {
  article_id: number
  title: string
  current: number
  total: number
}

interface CompletedArticle {
  article_id: number
  title: string
  success_count: number
  fail_count: number
  timestamp: string
}

export function QueuePage() {
  const [paused, setPaused] = useState(false)
  const [current, setCurrent] = useState<CurrentProgress | null>(null)
  const [pending, setPending] = useState<{ article_id: number; channel_slug: string }[]>([])
  const [completed, setCompleted] = useState<CompletedArticle[]>([])

  // 초기 상태 로드
  useEffect(() => {
    backupApi.getQueue().then(status => {
      setPaused(status.paused)
      setPending(status.pending)
      if (status.current) {
        setCurrent({
          article_id: status.current.article_id,
          title: `#${status.current.article_id}`,
          current: 0,
          total: 0,
        })
      }
    })
  }, [])

  // SSE 이벤트
  useSSE('/api/backup/events', {
    queue_updated: (data: unknown) => {
      const d = data as { queue: { article_id: number; channel_slug: string }[] }
      setPending(d.queue)
    },
    article_started: (data: unknown) => {
      const d = data as SSEArticleStarted
      setCurrent({
        article_id: d.article_id,
        title: d.title,
        current: 0,
        total: d.total_files,
      })
    },
    file_completed: (data: unknown) => {
      const d = data as SSEFileCompleted
      setCurrent(prev =>
        prev && prev.article_id === d.article_id
          ? { ...prev, current: d.current, total: d.total }
          : prev
      )
    },
    article_completed: (data: unknown) => {
      const d = data as SSEArticleCompleted
      setCurrent(prev => {
        if (prev && prev.article_id === d.article_id) {
          setCompleted(list => [{
            article_id: d.article_id,
            title: prev.title,
            success_count: d.success_count,
            fail_count: d.fail_count,
            timestamp: new Date().toLocaleTimeString('ko-KR'),
          }, ...list])
          return null
        }
        return prev
      })
    },
    worker_paused: () => setPaused(true),
    worker_resumed: () => setPaused(false),
  })

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">다운로드 큐</h1>

      <QueuePanel
        paused={paused}
        current={current}
        pending={pending}
        onPause={() => backupApi.pause()}
        onResume={() => backupApi.resume()}
        onCancel={(id) => backupApi.cancel(id)}
      />

      {/* 최근 완료 */}
      {completed.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">최근 완료</h2>
          {completed.map(item => (
            <div key={`${item.article_id}-${item.timestamp}`} className="flex justify-between text-sm py-1 border-b">
              <span>{item.title}</span>
              <span className="text-muted-foreground">
                {item.success_count} 성공
                {item.fail_count > 0 && `, ${item.fail_count} 실패`}
                {' · '}{item.timestamp}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: App.tsx 업데이트**

```tsx
import { QueuePage } from '@/pages/QueuePage'

// Routes 내:
<Route path="/queue" element={<QueuePage />} />
```

- [ ] **Step 4: 개발 서버 확인**

`http://localhost:5173/queue`에서 큐 상태가 표시되고, 게시글을 백업 큐에 추가하면 SSE로 실시간 진행도가 보이는지 확인.

- [ ] **Step 5: 커밋**

```bash
cd /Users/user/project/snuff/sentinel
git add web/src/
git commit -m "feat: add download queue page with SSE real-time progress"
```

---

### Task 7: 백업 이력 페이지

**Files:**
- Create: `web/src/pages/HistoryPage.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 이력 페이지**

`web/src/pages/HistoryPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { backupApi } from '@/api/client'
import type { BackupHistoryItem } from '@/api/types'

const STATUS_LABELS: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  completed: { label: '완료', variant: 'default' },
  failed: { label: '실패', variant: 'destructive' },
  cancelled: { label: '취소', variant: 'secondary' },
  pending: { label: '대기', variant: 'outline' },
  in_progress: { label: '진행중', variant: 'outline' },
}

export function HistoryPage() {
  const [items, setItems] = useState<BackupHistoryItem[]>([])
  const [filter, setFilter] = useState<string | undefined>()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    backupApi.getHistory(filter)
      .then(setItems)
      .finally(() => setLoading(false))
  }, [filter])

  const handleRetry = async (item: BackupHistoryItem) => {
    await backupApi.enqueue(item.channel_slug, item.id, true)
    alert('백업 큐에 다시 추가했습니다.')
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">백업 이력</h1>

      {/* 필터 */}
      <div className="flex gap-2">
        {[undefined, 'completed', 'failed', 'cancelled'].map(status => (
          <Button
            key={status ?? 'all'}
            variant={filter === status ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(status)}
          >
            {status ? STATUS_LABELS[status]?.label ?? status : '전체'}
          </Button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-8 text-muted-foreground">로딩 중...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">이력이 없습니다.</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-20">ID</TableHead>
              <TableHead>제목</TableHead>
              <TableHead className="w-24">작성자</TableHead>
              <TableHead className="w-20">상태</TableHead>
              <TableHead className="w-40">백업 시각</TableHead>
              <TableHead className="w-20"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map(item => {
              const statusInfo = STATUS_LABELS[item.backup_status] ?? { label: item.backup_status, variant: 'outline' as const }
              return (
                <TableRow key={item.id}>
                  <TableCell className="text-muted-foreground">{item.id}</TableCell>
                  <TableCell>
                    <div>{item.title}</div>
                    {item.backup_error && (
                      <div className="text-xs text-destructive mt-0.5">{item.backup_error}</div>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">{item.author}</TableCell>
                  <TableCell>
                    <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {item.backed_up_at
                      ? new Date(item.backed_up_at).toLocaleString('ko-KR')
                      : '—'}
                  </TableCell>
                  <TableCell>
                    {item.backup_status === 'failed' && (
                      <Button size="sm" variant="ghost" onClick={() => handleRetry(item)}>
                        재시도
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
```

- [ ] **Step 2: App.tsx 최종 업데이트**

`web/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { ChannelInput } from '@/components/ChannelInput'
import { ChannelPage } from '@/pages/ChannelPage'
import { ArticleDetailPage } from '@/pages/ArticleDetailPage'
import { QueuePage } from '@/pages/QueuePage'
import { HistoryPage } from '@/pages/HistoryPage'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background">
        <nav className="border-b px-6 py-3 flex items-center gap-4">
          <Link to="/" className="font-bold text-lg">Sentinel</Link>
          <Link to="/queue" className="text-muted-foreground hover:text-foreground">큐</Link>
          <Link to="/history" className="text-muted-foreground hover:text-foreground">이력</Link>
        </nav>
        <main className="p-6">
          <Routes>
            <Route path="/" element={
              <div className="space-y-6">
                <h1 className="text-2xl font-bold">채널 입력</h1>
                <ChannelInput />
              </div>
            } />
            <Route path="/channel/:slug" element={<ChannelPage />} />
            <Route path="/article/:slug/:id" element={<ArticleDetailPage />} />
            <Route path="/queue" element={<QueuePage />} />
            <Route path="/history" element={<HistoryPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
```

- [ ] **Step 3: 빌드 확인**

```bash
cd web && npm run build
```

`web/dist/` 폴더가 생성되었는지 확인. FastAPI 서버를 재시작하면 `http://localhost:8000/`에서 React 앱이 서빙됨.

- [ ] **Step 4: 커밋**

```bash
cd /Users/user/project/snuff/sentinel
git add web/src/
git commit -m "feat: add history page + finalize all frontend pages"
```
