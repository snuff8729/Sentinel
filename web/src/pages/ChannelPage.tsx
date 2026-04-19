import { useCallback, useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ArticleList } from '@/components/ArticleList'
import { channelApi, backupApi } from '@/api/client'
import type { ArticleList as ArticleListType, Category, ChannelInfo } from '@/api/types'
import { addRecentChannel } from '@/lib/recentChannels'
import { useSSE } from '@/hooks/useSSE'
import type { SSEArticleStarted, SSEArticleCompleted } from '@/api/types'

export function ChannelPage() {
  const { slug } = useParams<{ slug: string }>()
  const [searchParams, setSearchParams] = useSearchParams()

  const [channelInfo, setChannelInfo] = useState<ChannelInfo | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [data, setData] = useState<ArticleListType | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [keyword, setKeyword] = useState('')
  const [searchTarget, setSearchTarget] = useState('전체')
  const [loading, setLoading] = useState(false)
  const [backupStatuses, setBackupStatuses] = useState<Record<string, string>>({})

  const SEARCH_TARGETS: Record<string, string> = {
    '전체': 'all',
    '제목/내용': 'title_content',
    '제목': 'title',
    '내용': 'content',
    '글쓴이': 'nickname',
    '댓글': 'comment',
  }

  // SSE로 백업 상태 실시간 업데이트
  const updateStatus = useCallback((articleId: number, status: string) => {
    setBackupStatuses(prev => ({ ...prev, [String(articleId)]: status }))
  }, [])

  useSSE('/api/backup/events', {
    queue_updated: () => {},
    article_started: (data: unknown) => {
      const d = data as SSEArticleStarted
      updateStatus(d.article_id, 'in_progress')
    },
    article_completed: (data: unknown) => {
      const d = data as SSEArticleCompleted
      updateStatus(d.article_id, d.fail_count > 0 ? 'failed' : 'completed')
    },
    worker_paused: () => {},
    worker_resumed: () => {},
  })

  const category = searchParams.get('category') || undefined
  const mode = searchParams.get('mode') || undefined
  const page = Number(searchParams.get('page') || '1')

  useEffect(() => {
    if (!slug) return
    channelApi.getInfo(slug).then(info => {
      setChannelInfo(info)
      addRecentChannel(slug, info.name, info.icon_url ?? undefined)
    })
    channelApi.getCategories(slug).then(setCategories)
  }, [slug])

  useEffect(() => {
    if (!slug) return
    setLoading(true)
    setSelected(new Set())
    channelApi.getArticles(slug, { category, mode, page })
      .then(result => {
        setData(result)
        const ids = result.articles.map(a => a.id)
        if (ids.length > 0) {
          backupApi.getStatuses(ids).then(setBackupStatuses)
        } else {
          setBackupStatuses({})
        }
      })
      .finally(() => setLoading(false))
  }, [slug, category, mode, page])

  const doSearch = (searchKeyword: string, target: string) => {
    if (!slug || !searchKeyword.trim()) return
    setLoading(true)
    channelApi.search(slug, searchKeyword, target)
      .then(result => {
        setData(result)
        const ids = result.articles.map(a => a.id)
        if (ids.length > 0) {
          backupApi.getStatuses(ids).then(setBackupStatuses)
        } else {
          setBackupStatuses({})
        }
      })
      .finally(() => setLoading(false))
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    doSearch(keyword, SEARCH_TARGETS[searchTarget] || 'all')
  }

  const handleSearchAuthor = (author: string) => {
    setKeyword(author)
    setSearchTarget('글쓴이')
    doSearch(author, 'nickname')
  }

  const updateParams = (updates: Record<string, string | undefined>) => {
    const params = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(updates)) {
      if (v) params.set(k, v)
      else params.delete(k)
    }
    params.delete('page')
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
    const count = selected.size
    for (const id of selected) {
      await backupApi.enqueue(slug, id)
      updateStatus(id, 'pending')
    }
    setSelected(new Set())
    alert(`${count}개 게시글을 백업 큐에 추가했습니다.`)
  }

  const setPage = (p: number) => {
    const params = new URLSearchParams(searchParams)
    params.set('page', String(p))
    setSearchParams(params)
  }

  if (!slug) return null

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        {channelInfo?.icon_url && (
          <img src={channelInfo.icon_url} alt="" className="w-8 h-8 rounded" referrerPolicy="no-referrer" />
        )}
        <h1 className="text-2xl font-bold">{channelInfo?.name ?? slug}</h1>
      </div>

      <div className="flex flex-wrap gap-1">
        <Button
          variant={!category ? 'default' : 'ghost'}
          size="sm"
          onClick={() => updateParams({ category: undefined })}
        >
          전체
        </Button>
        {categories.filter(c => c.slug).map(c => (
          <Button
            key={c.slug}
            variant={category === c.slug ? 'default' : 'ghost'}
            size="sm"
            onClick={() => updateParams({ category: c.slug })}
          >
            {c.name}
          </Button>
        ))}
      </div>

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
          <Select value={searchTarget} onValueChange={(v) => v && setSearchTarget(v)}>
            <SelectTrigger className="w-28">
              <SelectValue placeholder="전체" />
            </SelectTrigger>
            <SelectContent>
              {Object.keys(SEARCH_TARGETS).map(label => (
                <SelectItem key={label} value={label}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="검색..."
            className="w-48"
          />
          <Button type="submit" size="sm" variant="outline">검색</Button>
        </form>
      </div>

      {selected.size > 0 && (
        <div className="flex items-center gap-2 p-2 bg-muted rounded">
          <span className="text-sm">{selected.size}개 선택</span>
          <Button size="sm" onClick={handleBackup}>백업 큐에 추가</Button>
        </div>
      )}

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
            backupStatuses={backupStatuses}
            onSearchAuthor={handleSearchAuthor}
          />
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
