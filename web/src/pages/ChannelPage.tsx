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
import { channelApi, backupApi, followApi, settingsApi } from '@/api/client'
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
  const [keywordInput, setKeywordInput] = useState('')
  const [targetInput, setTargetInput] = useState('전체')
  const [loading, setLoading] = useState(false)
  const [backupStatuses, setBackupStatuses] = useState<Record<string, string>>({})
  const [followedUsers, setFollowedUsers] = useState<Set<string>>(new Set())
  const [updateCandidates, setUpdateCandidates] = useState<Record<number, { matched_title: string; group_name: string | null; reason: string }>>({})
  const [updateDetectEnabled, setUpdateDetectEnabled] = useState(false)
  const [updateDetecting, setUpdateDetecting] = useState(false)
  const [updateDetectError, setUpdateDetectError] = useState('')

  const SEARCH_TARGETS: Record<string, string> = {
    '전체': 'all',
    '제목/내용': 'title_content',
    '제목': 'title',
    '내용': 'content',
    '글쓴이': 'nickname',
    '댓글': 'comment',
  }

  const TARGET_LABELS: Record<string, string> = Object.fromEntries(
    Object.entries(SEARCH_TARGETS).map(([k, v]) => [v, k])
  )

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
  const keyword = searchParams.get('keyword') || undefined
  const target = searchParams.get('target') || undefined

  useEffect(() => {
    if (!slug) return
    channelApi.getInfo(slug).then(info => {
      setChannelInfo(info)
      addRecentChannel(slug, info.name, info.icon_url ?? undefined)
    })
    channelApi.getCategories(slug).then(setCategories)
    followApi.usernames().then(u => setFollowedUsers(new Set(u)))
  }, [slug])

  // URL 파라미터가 바뀔 때마다 데이터 로드 (검색 포함)
  useEffect(() => {
    if (!slug) return
    setLoading(true)
    setSelected(new Set())

    const fetchData = keyword
      ? channelApi.search(slug, keyword, target || 'all', page, { category, mode })
      : channelApi.getArticles(slug, { category, mode, page })

    fetchData
      .then(result => {
        setData(result)
        const ids = result.articles.map(a => a.id)
        if (ids.length > 0) {
          backupApi.getStatuses(ids).then(setBackupStatuses)
        } else {
          setBackupStatuses({})
        }
        // 업데이트 감지 비활성화면 스킵
        setUpdateCandidates({})
      })
      .finally(() => setLoading(false))
  }, [slug, category, mode, page, keyword, target])

  // 업데이트 감지 (토글 활성화 시)
  useEffect(() => {
    if (!updateDetectEnabled || !slug || !data) return
    setUpdateDetecting(true)
    const articlesForCheck = data.articles.map(a => ({ id: a.id, title: a.title, author: a.author }))
    channelApi.checkUpdates(slug, articlesForCheck).then(res => {
      const map: Record<number, { matched_title: string; group_name: string | null; reason: string }> = {}
      for (const u of res.updates) {
        map[u.article_id] = { matched_title: u.matched_title, group_name: u.group_name, reason: u.reason }
      }
      setUpdateCandidates(map)
    }).catch(() => {}).finally(() => setUpdateDetecting(false))
  }, [updateDetectEnabled, data, slug])

  // URL 파라미터에서 검색 입력 필드 동기화
  useEffect(() => {
    setKeywordInput(keyword || '')
    setTargetInput(TARGET_LABELS[target || 'all'] || '전체')
  }, [keyword, target])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!keywordInput.trim()) return
    updateParams({ keyword: keywordInput, target: SEARCH_TARGETS[targetInput] || 'all' })
  }

  const handleSearchAuthor = (author: string) => {
    updateParams({ keyword: author, target: 'nickname' })
  }

  const handleToggleFollow = async (username: string) => {
    if (followedUsers.has(username)) {
      await followApi.unfollow(username)
      setFollowedUsers(prev => { const next = new Set(prev); next.delete(username); return next })
    } else {
      await followApi.follow(username)
      setFollowedUsers(prev => new Set(prev).add(username))
    }
  }

  const handleClearSearch = () => {
    updateParams({ keyword: undefined, target: undefined })
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
        <Button
          variant={updateDetectEnabled ? 'default' : 'outline'}
          size="sm"
          onClick={async () => {
            if (!updateDetectEnabled) {
              setUpdateDetectError('')
              const embedding = await settingsApi.getEmbedding()
              if (!embedding.base_url) {
                setUpdateDetectError('임베딩이 설정되지 않았습니다. 설정 페이지에서 구성해주세요.')
                return
              }
            }
            setUpdateDetectEnabled(!updateDetectEnabled)
            if (updateDetectEnabled) setUpdateDetectError('')
          }}
          disabled={updateDetecting}
        >
          {updateDetecting ? '감지 중...' : updateDetectEnabled ? '🔄 업데이트 감지 ON' : '업데이트 감지'}
        </Button>
        <div className="flex-1" />
        <form onSubmit={handleSearch} className="flex gap-2">
          <Select value={targetInput} onValueChange={(v) => v && setTargetInput(v)}>
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
            value={keywordInput}
            onChange={e => setKeywordInput(e.target.value)}
            placeholder="검색..."
            className="w-48"
          />
          <Button type="submit" size="sm" variant="outline">검색</Button>
          {keyword && (
            <Button type="button" size="sm" variant="ghost" onClick={handleClearSearch}>✕</Button>
          )}
        </form>
      </div>

      {updateDetectError && (
        <div className="text-sm p-3 rounded border bg-yellow-50 border-yellow-200 text-yellow-700 flex items-center gap-2">
          <span>⚠ {updateDetectError}</span>
          <a href="/settings" className="text-blue-600 hover:underline text-xs">설정으로 이동</a>
        </div>
      )}

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
            followedUsers={followedUsers}
            onToggleFollow={handleToggleFollow}
            updateCandidates={updateCandidates}
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
