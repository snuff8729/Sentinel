import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { backupApi } from '@/api/client'
import { useSSE } from '@/hooks/useSSE'
import { ComboboxFilter } from '@/components/ComboboxFilter'
import type { ArticleFileItem, ArticleLinkItem, BackupHistoryItem, SSEArticleStarted, SSEArticleCompleted } from '@/api/types'

type SortKey = 'backed_up_at' | 'created_at' | 'title' | 'author'
type SortDir = 'asc' | 'desc'

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'backed_up_at', label: '백업일시' },
  { value: 'created_at', label: '게시일' },
  { value: 'title', label: '제목' },
  { value: 'author', label: '작성자' },
]

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  completed: { label: '완료', className: 'bg-green-100 text-green-700 border-green-300' },
  failed: { label: '실패', className: 'bg-red-100 text-red-700 border-red-300' },
  in_progress: { label: '진행중', className: 'bg-blue-100 text-blue-700 border-blue-300 animate-pulse' },
  pending: { label: '대기', className: 'bg-yellow-100 text-yellow-700 border-yellow-300' },
  cancelled: { label: '취소', className: 'bg-gray-100 text-gray-500 border-gray-300' },
}

const PAGE_SIZE = 50

export function HistoryPage() {
  const [items, setItems] = useState<BackupHistoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [searchParams, setSearchParams] = useSearchParams()
  const filter = searchParams.get('filter') ?? undefined
  const sortKey = (searchParams.get('sort') as SortKey | null) ?? 'backed_up_at'
  const sortDir = (searchParams.get('dir') as SortDir | null) ?? 'desc'
  const page = parseInt(searchParams.get('page') ?? '1', 10) || 1
  const channelFilter = searchParams.get('channel') ?? undefined
  const categoryFilter = searchParams.get('category')  // null = 필터 없음, "" = 카테고리 없음, 기타 = 특정 카테고리
  const updateParams = (next: { filter?: string; sort?: SortKey; dir?: SortDir; page?: number; channel?: string | null; category?: string | null }) => {
    const params: Record<string, string> = {}
    const f = next.filter !== undefined ? next.filter : filter
    const s = next.sort !== undefined ? next.sort : sortKey
    const d = next.dir !== undefined ? next.dir : sortDir
    const p = next.page !== undefined ? next.page : page
    const ch = next.channel !== undefined ? next.channel : channelFilter
    const cat = next.category !== undefined ? next.category : categoryFilter
    if (f) params.filter = f
    if (s && s !== 'backed_up_at') params.sort = s
    if (d && d !== 'desc') params.dir = d
    if (p && p !== 1) params.page = String(p)
    if (ch) params.channel = ch
    if (cat !== null && cat !== undefined) params.category = cat
    setSearchParams(params)
  }
  const setFilter = (next: string | undefined) => updateParams({ filter: next ?? '', page: 1 })
  const [categoryOptions, setCategoryOptions] = useState<{ channel_slug: string; category: string; count: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [expandedLinks, setExpandedLinks] = useState<ArticleLinkItem[]>([])
  const [expandedFiles, setExpandedFiles] = useState<ArticleFileItem[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  const isStatusFilter = filter !== undefined && filter !== 'download_incomplete'
  const load = useCallback(() => {
    setLoading(true)
    backupApi.getHistory({
      status: isStatusFilter ? filter : undefined,
      filter: filter === 'download_incomplete' ? 'download_incomplete' : undefined,
      channel_slug: channelFilter,
      category: categoryFilter ?? undefined,
      page,
      size: PAGE_SIZE,
      sort: sortKey,
      dir: sortDir,
    })
      .then(res => {
        setItems(res.items)
        setTotal(res.total)
      })
      .finally(() => setLoading(false))
  }, [filter, isStatusFilter, channelFilter, categoryFilter, page, sortKey, sortDir])

  useEffect(() => { load() }, [load])

  // 카테고리 드롭다운 옵션 (마운트 시 1회)
  useEffect(() => {
    backupApi.getHistoryCategories().then(setCategoryOptions).catch(() => setCategoryOptions([]))
  }, [])

  useSSE('/api/backup/events', {
    queue_updated: () => {},
    article_started: (data: unknown) => {
      const d = data as SSEArticleStarted
      const exists = items.some(item => item.id === d.article_id)
      if (exists) {
        setItems(prev => prev.map(item =>
          item.id === d.article_id
            ? { ...item, backup_status: 'in_progress', backup_error: null }
            : item
        ))
      } else {
        // 현재 페이지에 없는 새 항목 — 서버 정렬·페이지 유지 위해 재페칭
        load()
      }
    },
    article_completed: (data: unknown) => {
      const d = data as SSEArticleCompleted
      const status = d.fail_count > 0 ? 'failed' : 'completed'
      setItems(prev =>
        prev.map(item =>
          item.id === d.article_id
            ? { ...item, backup_status: status, backed_up_at: new Date().toISOString() }
            : item
        )
      )
      if (expandedId === d.article_id) {
        backupApi.getDetail(d.article_id).then(detail => {
          setExpandedLinks(detail.links ?? [])
          setExpandedFiles(detail.files ?? [])
        })
      }
    },
    worker_paused: () => {},
    worker_resumed: () => {},
  })

  const handleToggleDetail = async (articleId: number) => {
    if (expandedId === articleId) {
      setExpandedId(null)
      setExpandedLinks([])
      setExpandedFiles([])
      return
    }
    setExpandedId(articleId)
    setDetailLoading(true)
    try {
      const detail = await backupApi.getDetail(articleId)
      setExpandedLinks(detail.links ?? [])
      setExpandedFiles(detail.files ?? [])
    } finally {
      setDetailLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">백업 이력</h1>

      {/* 필터 */}
      <div className="flex flex-wrap gap-2">
        {[undefined, 'completed', 'failed', 'cancelled', 'pending', 'in_progress'].map(status => (
          <Button
            key={status ?? 'all'}
            variant={filter === status ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(status)}
          >
            {status ? STATUS_BADGE[status]?.label ?? status : '전체'}
          </Button>
        ))}
        <Button
          variant={filter === 'download_incomplete' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter(filter === 'download_incomplete' ? undefined : 'download_incomplete')}
        >
          다운로드 미완료
        </Button>
      </div>

      {/* 카테고리 + 정렬 */}
      <div className="flex items-center gap-4 text-sm flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">카테고리</span>
          <ComboboxFilter
            value={channelFilter && categoryFilter !== null ? `${channelFilter}||${categoryFilter}` : null}
            options={categoryOptions.map(opt => ({
              value: `${opt.channel_slug}||${opt.category}`,
              label: `${opt.channel_slug} / ${opt.category || '(없음)'} (${opt.count})`,
            }))}
            onChange={(v) => {
              if (v === null) {
                updateParams({ channel: null, category: null, page: 1 })
                return
              }
              const [ch, cat] = v.split('||')
              updateParams({ channel: ch, category: cat, page: 1 })
            }}
            placeholder="전체"
            searchPlaceholder="채널/카테고리 검색..."
            triggerClassName="w-64"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">정렬</span>
          <Select value={sortKey} onValueChange={(v) => v && updateParams({ sort: v as SortKey, page: 1 })}>
          <SelectTrigger className="w-32 h-8 text-xs">
            <SelectValue>
              {(v) => SORT_OPTIONS.find(o => o.value === v)?.label ?? v}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map(opt => (
              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => updateParams({ dir: sortDir === 'desc' ? 'asc' : 'desc', page: 1 })}
            title={sortDir === 'desc' ? '내림차순' : '오름차순'}
          >
            {sortDir === 'desc' ? '↓' : '↑'}
          </Button>
        </div>
      </div>

      {/* 수동 다운로드 대기 요약 */}
      {!loading && filter !== 'download_incomplete' && items.some(i => i.backup_status === 'completed' && !i.download_complete && i.analysis_status !== 'none') && (
        <div className="text-sm p-3 rounded border bg-amber-50 border-amber-200 text-amber-700">
          ⚠ 이 페이지에 수동 다운로드가 필요한 항목이 있습니다. '다운로드 미완료' 필터로 전체 목록을 볼 수 있습니다.
        </div>
      )}

      {loading ? (
        <div className="text-center py-8 text-muted-foreground">로딩 중...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">이력이 없습니다.</div>
      ) : (
        <div className="border rounded-md">
          {items.map(item => {
            const badgeInfo = STATUS_BADGE[item.backup_status] ?? { label: item.backup_status, className: 'bg-gray-100 text-gray-500 border-gray-300' }
            const isExpanded = expandedId === item.id

            return (
              <div key={item.id} className="border-b last:border-b-0">
                {/* 메인 행 */}
                <div
                  className="flex items-start gap-3 px-3 py-2.5 hover:bg-muted/30 cursor-pointer"
                  onClick={() => handleToggleDetail(item.id)}
                >
                  <span className="text-muted-foreground text-xs pt-1.5">
                    {isExpanded ? '▼' : '▶'}
                  </span>
                  <div className="flex-1 min-w-0">
                    {/* 윗줄: 상태 + 제목 */}
                    <div className="leading-snug">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border mr-1.5 align-middle ${badgeInfo.className}`}>
                        {badgeInfo.label}
                      </span>
                      {item.backup_status === 'completed' && item.download_complete === false && item.analysis_status !== 'none' && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border mr-1.5 align-middle bg-red-100 text-red-700 border-red-300">
                          다운로드 미완료
                        </span>
                      )}
                      {item.download_complete && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border mr-1.5 align-middle bg-emerald-100 text-emerald-700 border-emerald-300">
                          다운로드 완료
                        </span>
                      )}
                      <Link
                        to={`/backup/${item.id}`}
                        className="align-middle hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {item.title}
                      </Link>
                    </div>
                    {item.backup_error && (
                      <div className="text-xs text-destructive mt-0.5">{item.backup_error}</div>
                    )}

                    {/* 아랫줄: 작성자 + 채널 + 백업 시각 */}
                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                      <span>{item.author || '—'}</span>
                      {item.channel_slug && (
                        <>
                          <span>·</span>
                          <span>{item.channel_slug}</span>
                        </>
                      )}
                      <span>·</span>
                      <span>
                        {item.backed_up_at
                          ? new Date(item.backed_up_at).toLocaleString('ko-KR')
                          : '—'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 상세 펼침: 자료 (링크 + 첨부 파일) */}
                {isExpanded && (
                  <div className="bg-muted/30 border-t px-4 py-3">
                    {detailLoading ? (
                      <div className="text-center py-4 text-sm text-muted-foreground">로딩 중...</div>
                    ) : (() => {
                      const downloadLinks = expandedLinks.filter(l => l.type === 'download')
                      if (downloadLinks.length === 0 && expandedFiles.length === 0) {
                        return <div className="text-sm text-muted-foreground py-2">자료가 없습니다.</div>
                      }
                      return (
                      <div className="space-y-3">
                        {downloadLinks.length > 0 && (
                          <div className="space-y-1">
                            <div className="text-xs font-medium text-muted-foreground">다운로드 링크 {downloadLinks.length}개</div>
                            <div className="max-h-60 overflow-y-auto border rounded bg-background">
                              {downloadLinks.map(l => (
                                <div key={l.id} className="flex items-center gap-3 px-3 py-1.5 border-b last:border-b-0 text-xs hover:bg-muted/20">
                                  <a href={l.url} target="_blank" rel="noopener noreferrer" className="flex-1 truncate text-blue-600 hover:underline" title={l.url}>
                                    {l.label || l.url}
                                  </a>
                                  {l.download_status && (
                                    <span className={`w-16 text-right ${l.download_status === 'completed' ? 'text-green-600' : l.download_status === 'failed' ? 'text-red-600' : 'text-muted-foreground'}`}>
                                      {l.download_status}
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {expandedFiles.length > 0 && (
                          <div className="space-y-1">
                            <div className="text-xs font-medium text-muted-foreground">첨부 파일 {expandedFiles.length}개</div>
                            <div className="max-h-60 overflow-y-auto border rounded bg-background">
                              {expandedFiles.map(f => {
                                const sizeLabel = f.size >= 1024 * 1024
                                  ? `${(f.size / 1024 / 1024).toFixed(1)}MB`
                                  : `${(f.size / 1024).toFixed(1)}KB`
                                return (
                                  <div key={f.id} className="flex items-center gap-3 px-3 py-1.5 border-b last:border-b-0 text-xs hover:bg-muted/20">
                                    <span className="font-mono truncate flex-1" title={f.filename}>{f.filename}</span>
                                    <span className="w-16 text-right text-muted-foreground">{sizeLabel}</span>
                                    {f.note && <span className="truncate max-w-[200px] text-muted-foreground">{f.note}</span>}
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                      )
                    })()}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* 페이지네이션 */}
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} / {total}
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm" variant="outline"
              disabled={page <= 1}
              onClick={() => updateParams({ page: page - 1 })}
            >
              이전
            </Button>
            <span className="px-2">{page} / {Math.max(1, Math.ceil(total / PAGE_SIZE))}</span>
            <Button
              size="sm" variant="outline"
              disabled={page >= Math.ceil(total / PAGE_SIZE)}
              onClick={() => updateParams({ page: page + 1 })}
            >
              다음
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
