import { useCallback, useEffect, useState } from 'react'
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
import { useSSE } from '@/hooks/useSSE'
import type { BackupHistoryItem, DownloadItem, SSEArticleStarted, SSEArticleCompleted } from '@/api/types'

const STATUS_LABELS: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  completed: { label: '완료', variant: 'default' },
  failed: { label: '실패', variant: 'destructive' },
  cancelled: { label: '취소', variant: 'secondary' },
  pending: { label: '대기', variant: 'outline' },
  in_progress: { label: '진행중', variant: 'outline' },
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

  const refreshHistory = useCallback(() => {
    backupApi.getHistory(filter).then(setItems)
  }, [filter])

  useEffect(() => {
    setLoading(true)
    backupApi.getHistory(filter)
      .then(setItems)
      .finally(() => setLoading(false))
  }, [filter])

  // SSE로 실시간 업데이트
  useSSE('/api/backup/events', {
    queue_updated: () => {},
    article_started: (data: unknown) => {
      const d = data as SSEArticleStarted
      // 이력에 in_progress 항목 추가/업데이트
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
      // 상세가 열려있으면 다운로드 목록도 갱신
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

  const handleRetry = async (item: BackupHistoryItem) => {
    await backupApi.enqueue(item.channel_slug, item.id, true)
    alert('백업 큐에 다시 추가했습니다.')
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">백업 이력</h1>

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
              const isExpanded = expandedId === item.id
              return (
                <>
                  <TableRow
                    key={item.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleToggleDetail(item.id)}
                  >
                    <TableCell className="text-muted-foreground">{item.id}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <span className="text-muted-foreground text-xs">{isExpanded ? '▼' : '▶'}</span>
                        <span>{item.title}</span>
                      </div>
                      {item.backup_error && (
                        <div className="text-xs text-destructive mt-0.5 ml-4">{item.backup_error}</div>
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
                    <TableCell onClick={e => e.stopPropagation()}>
                      {item.backup_status === 'failed' && (
                        <Button size="sm" variant="ghost" onClick={() => handleRetry(item)}>
                          재시도
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                  {isExpanded && (
                    <TableRow key={`${item.id}-detail`}>
                      <TableCell colSpan={6} className="bg-muted/30 p-0">
                        {detailLoading ? (
                          <div className="text-center py-4 text-sm text-muted-foreground">로딩 중...</div>
                        ) : (
                          <div className="p-4 space-y-2">
                            <div className="text-sm font-medium mb-2">
                              파일 {downloads.length}개
                              {(() => {
                                const failed = downloads.filter(d => d.status === 'failed').length
                                const warned = downloads.filter(d => d.warning).length
                                const parts = []
                                if (failed > 0) parts.push(<span key="f" className="text-red-600">{failed} 실패</span>)
                                if (warned > 0) parts.push(<span key="w" className="text-yellow-600">{warned} 경고</span>)
                                return parts.length > 0 ? <> — {parts.reduce<React.ReactNode[]>((acc, el, i) => i === 0 ? [el] : [...acc, ', ', el], [])}</> : null
                              })()}
                            </div>
                            <div className="max-h-80 overflow-y-auto border rounded">
                              <table className="w-full text-xs">
                                <thead className="sticky top-0 bg-background">
                                  <tr className="border-b">
                                    <th className="text-left py-1.5 px-2 font-medium">파일</th>
                                    <th className="text-left py-1.5 px-2 w-16 font-medium">타입</th>
                                    <th className="text-left py-1.5 px-2 w-16 font-medium">상태</th>
                                    <th className="text-left py-1.5 px-2 font-medium">비고</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {downloads.map(d => {
                                    const dlStatus = DL_STATUS[d.status] ?? { label: d.status, color: '' }
                                    return (
                                      <tr key={d.id} className="border-b last:border-b-0 hover:bg-muted/20">
                                        <td className="py-1.5 px-2 truncate max-w-xs font-mono" title={d.url}>
                                          {d.local_path.split('/').pop()}
                                        </td>
                                        <td className="py-1.5 px-2">{d.file_type}</td>
                                        <td className={`py-1.5 px-2 font-medium ${dlStatus.color}`}>
                                          {dlStatus.label}
                                        </td>
                                        <td className="py-1.5 px-2">
                                          {d.error && (
                                            <span className="text-red-600">{d.error}</span>
                                          )}
                                          {d.warning && (
                                            <span className="text-yellow-600">⚠ {d.warning}</span>
                                          )}
                                        </td>
                                      </tr>
                                    )
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  )}
                </>
              )
            })}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
