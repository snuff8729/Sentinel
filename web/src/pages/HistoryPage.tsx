import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { backupApi } from '@/api/client'
import { useSSE } from '@/hooks/useSSE'
import type { BackupHistoryItem, DownloadItem, SSEArticleStarted, SSEArticleCompleted } from '@/api/types'

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  completed: { label: '완료', className: 'bg-green-100 text-green-700 border-green-300' },
  failed: { label: '실패', className: 'bg-red-100 text-red-700 border-red-300' },
  in_progress: { label: '진행중', className: 'bg-blue-100 text-blue-700 border-blue-300 animate-pulse' },
  pending: { label: '대기', className: 'bg-yellow-100 text-yellow-700 border-yellow-300' },
  cancelled: { label: '취소', className: 'bg-gray-100 text-gray-500 border-gray-300' },
}

const DL_STATUS: Record<string, { label: string; color: string }> = {
  completed: { label: '완료', color: 'text-green-600' },
  failed: { label: '실패', color: 'text-red-600' },
  pending: { label: '대기', color: 'text-yellow-600' },
  in_progress: { label: '진행중', color: 'text-blue-600' },
}

export function HistoryPage() {
  const [items, setItems] = useState<BackupHistoryItem[]>([])
  const [filter, setFilter] = useState<string | undefined>()
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [downloads, setDownloads] = useState<DownloadItem[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    backupApi.getHistory(filter)
      .then(setItems)
      .finally(() => setLoading(false))
  }, [filter])

  useSSE('/api/backup/events', {
    queue_updated: () => {},
    article_started: (data: unknown) => {
      const d = data as SSEArticleStarted
      setItems(prev => {
        const exists = prev.some(item => item.id === d.article_id)
        if (exists) {
          return prev.map(item =>
            item.id === d.article_id
              ? { ...item, backup_status: 'in_progress', backup_error: null }
              : item
          )
        }
        return [{
          id: d.article_id,
          channel_slug: '',
          title: d.title,
          author: '',
          category: null,
          backup_status: 'in_progress',
          backup_error: null,
          backed_up_at: null,
        }, ...prev]
      })
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
        backupApi.getDetail(d.article_id).then(detail => setDownloads(detail.downloads))
      }
    },
    worker_paused: () => {},
    worker_resumed: () => {},
  })

  const handleToggleDetail = async (articleId: number) => {
    if (expandedId === articleId) {
      setExpandedId(null)
      setDownloads([])
      return
    }
    setExpandedId(articleId)
    setDetailLoading(true)
    try {
      const detail = await backupApi.getDetail(articleId)
      setDownloads(detail.downloads)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleRetry = async (e: React.MouseEvent, item: BackupHistoryItem) => {
    e.stopPropagation()
    await backupApi.enqueue(item.channel_slug, item.id, true)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">백업 이력</h1>

      {/* 필터 */}
      <div className="flex gap-2">
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
      </div>

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
                      <span className="align-middle">{item.title}</span>
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
                      <span>·</span>
                      <button
                        className="text-blue-500 hover:underline"
                        onClick={(e) => handleRetry(e, item)}
                      >
                        재시도
                      </button>
                    </div>
                  </div>
                </div>

                {/* 상세 펼침 */}
                {isExpanded && (
                  <div className="bg-muted/30 border-t px-4 py-3">
                    {detailLoading ? (
                      <div className="text-center py-4 text-sm text-muted-foreground">로딩 중...</div>
                    ) : (
                      <div className="space-y-2">
                        <div className="text-sm font-medium">
                          파일 {downloads.length}개
                          {(() => {
                            const failed = downloads.filter(d => d.status === 'failed').length
                            const warned = downloads.filter(d => d.warning).length
                            const parts: string[] = []
                            if (failed > 0) parts.push(`${failed} 실패`)
                            if (warned > 0) parts.push(`${warned} 경고`)
                            return parts.length > 0 ? ` — ${parts.join(', ')}` : ''
                          })()}
                        </div>
                        <div className="max-h-80 overflow-y-auto border rounded bg-background">
                          {downloads.map(d => {
                            const dlStatus = DL_STATUS[d.status] ?? { label: d.status, color: '' }
                            return (
                              <div key={d.id} className="flex items-center gap-3 px-3 py-1.5 border-b last:border-b-0 text-xs hover:bg-muted/20">
                                <span className="font-mono truncate flex-1" title={d.url}>
                                  {d.local_path.split('/').pop()}
                                </span>
                                <span className="w-14 text-muted-foreground">{d.file_type}</span>
                                <span className={`w-10 font-medium ${dlStatus.color}`}>{dlStatus.label}</span>
                                <span className="flex-1 truncate">
                                  {d.error && <span className="text-red-600">{d.error}</span>}
                                  {d.warning && <span className="text-yellow-600">⚠ {d.warning}</span>}
                                </span>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
