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
