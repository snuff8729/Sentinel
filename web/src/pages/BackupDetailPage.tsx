import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { backupApi } from '@/api/client'
import type { BackupDetail, DownloadItem } from '@/api/types'

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  completed: { label: '완료', className: 'bg-green-100 text-green-700 border-green-300' },
  failed: { label: '실패', className: 'bg-red-100 text-red-700 border-red-300' },
  in_progress: { label: '진행중', className: 'bg-blue-100 text-blue-700 border-blue-300' },
  pending: { label: '대기', className: 'bg-yellow-100 text-yellow-700 border-yellow-300' },
  cancelled: { label: '취소', className: 'bg-gray-100 text-gray-500 border-gray-300' },
}

const DL_STATUS: Record<string, { label: string; color: string }> = {
  completed: { label: '완료', color: 'text-green-600' },
  failed: { label: '실패', color: 'text-red-600' },
  pending: { label: '대기', color: 'text-yellow-600' },
  in_progress: { label: '진행중', color: 'text-blue-600' },
}

export function BackupDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [detail, setDetail] = useState<BackupDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'preview' | 'files'>('preview')

  useEffect(() => {
    if (!id) return
    setLoading(true)
    backupApi.getDetail(Number(id))
      .then(setDetail)
      .finally(() => setLoading(false))
  }, [id])

  const handleRetry = async () => {
    if (!detail) return
    await backupApi.enqueue(detail.article.channel_slug, detail.article.id, true)
    alert('백업 큐에 다시 추가했습니다.')
  }

  if (loading) return <div className="text-center py-8 text-muted-foreground">로딩 중...</div>
  if (!detail) return <div className="text-center py-8">백업 데이터를 찾을 수 없습니다.</div>

  const { article, downloads } = detail
  const badgeInfo = STATUS_BADGE[article.backup_status] ?? { label: article.backup_status, className: 'bg-gray-100 text-gray-500 border-gray-300' }
  const failedCount = downloads.filter(d => d.status === 'failed').length
  const warningCount = downloads.filter(d => d.warning).length

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* 헤더 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${badgeInfo.className}`}>
            {badgeInfo.label}
          </span>
          {article.category && <Badge variant="secondary">{article.category}</Badge>}
          <h1 className="text-2xl font-bold">{article.title}</h1>
        </div>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{article.author}</span>
          <span>{article.channel_slug}</span>
          {article.created_at && (
            <span>{new Date(article.created_at).toLocaleString('ko-KR')}</span>
          )}
          {article.backed_up_at && (
            <span>백업: {new Date(article.backed_up_at).toLocaleString('ko-KR')}</span>
          )}
        </div>
        {article.backup_error && (
          <div className="text-sm text-destructive">{article.backup_error}</div>
        )}
      </div>

      {/* 액션 */}
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" onClick={handleRetry}>재시도</Button>
        <Link to={`/article/${article.channel_slug}/${article.id}`}>
          <Button size="sm" variant="outline">원본 보기 (arca.live)</Button>
        </Link>
        {article.url && (
          <a href={article.url} target="_blank" rel="noopener noreferrer">
            <Button size="sm" variant="ghost">arca.live에서 열기 ↗</Button>
          </a>
        )}
      </div>

      {/* 탭 */}
      <div className="flex gap-1 border-b">
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'preview'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('preview')}
        >
          백업 미리보기
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'files'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('files')}
        >
          파일 ({downloads.length})
          {failedCount > 0 && <span className="text-red-500 ml-1">{failedCount} 실패</span>}
          {warningCount > 0 && <span className="text-yellow-500 ml-1">{warningCount} 경고</span>}
        </button>
      </div>

      {/* 탭 내용 */}
      {activeTab === 'preview' ? (
        <div className="border rounded-md overflow-hidden">
          <iframe
            src={`/api/backup/html/${article.id}`}
            className="w-full border-0"
            style={{ minHeight: '80vh' }}
            title="백업 미리보기"
          />
        </div>
      ) : (
        <FileList downloads={downloads} />
      )}
    </div>
  )
}

function FileList({ downloads }: { downloads: DownloadItem[] }) {
  return (
    <div className="border rounded-md">
      {downloads.map(d => {
        const dlStatus = DL_STATUS[d.status] ?? { label: d.status, color: '' }
        return (
          <div key={d.id} className="flex items-center gap-3 px-3 py-2 border-b last:border-b-0 text-sm hover:bg-muted/20">
            <span className="font-mono text-xs truncate flex-1" title={d.url}>
              {d.local_path.split('/').pop()}
            </span>
            <span className="w-16 text-xs text-muted-foreground">{d.file_type}</span>
            <span className={`w-12 text-xs font-medium ${dlStatus.color}`}>{dlStatus.label}</span>
            <span className="flex-1 text-xs truncate">
              {d.error && <span className="text-red-600">{d.error}</span>}
              {d.warning && <span className="text-yellow-600">⚠ {d.warning}</span>}
            </span>
          </div>
        )
      })}
    </div>
  )
}
