import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { QueuePanel } from '@/components/QueuePanel'
import { backupApi, savedImagesApi } from '@/api/client'
import type { SavedImageQueueSnapshot } from '@/api/client'
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

      {completed.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">최근 완료</h2>
          {completed.map(item => (
            <div key={`${item.article_id}-${item.timestamp}`} className="flex justify-between text-sm py-1 border-b">
              <Link to={`/backup/${item.article_id}`} className="hover:underline">{item.title}</Link>
              <span className="text-muted-foreground">
                {item.success_count} 성공
                {item.fail_count > 0 && `, ${item.fail_count} 실패`}
                {' · '}{item.timestamp}
              </span>
            </div>
          ))}
        </div>
      )}

      <SavedImageQueueSection />
    </div>
  )
}

function SavedImageQueueSection() {
  const [snap, setSnap] = useState<SavedImageQueueSnapshot | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    savedImagesApi
      .getQueue()
      .then(s => {
        if (!cancelled) {
          setSnap(s)
          setError(false)
        }
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useSSE('/api/saved-images/events', {
    saved_queue_updated: (data: unknown) => {
      setSnap(data as SavedImageQueueSnapshot)
      setError(false)
    },
  })

  if (error && snap == null) {
    return (
      <div className="space-y-2 border-t pt-4">
        <h2 className="text-lg font-semibold">이미지 다운로드</h2>
        <p className="text-sm text-destructive">큐 조회 실패</p>
      </div>
    )
  }
  if (snap == null) return null

  const total =
    snap.pending.length + snap.in_progress.length + snap.failed.length

  return (
    <div className="space-y-3 border-t pt-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">이미지 다운로드</h2>
        <span className="text-xs text-muted-foreground">
          진행 {snap.in_progress.length} · 대기 {snap.pending.length} · 실패{' '}
          {snap.failed.length}
        </span>
      </div>

      {total === 0 && snap.recent_completed.length === 0 && (
        <p className="text-sm text-muted-foreground">큐 비어있음</p>
      )}

      {snap.in_progress.length > 0 && (
        <SavedImageQueueList label="진행 중" rows={snap.in_progress} tone="active" />
      )}
      {snap.pending.length > 0 && (
        <SavedImageQueueList label="대기" rows={snap.pending} tone="pending" />
      )}
      {snap.failed.length > 0 && (
        <SavedImageQueueList label="실패" rows={snap.failed} tone="failed" />
      )}
      {snap.recent_completed.length > 0 && (
        <SavedImageQueueList
          label="최근 완료"
          rows={snap.recent_completed}
          tone="completed"
        />
      )}
    </div>
  )
}

function SavedImageQueueList({
  label,
  rows,
  tone,
}: {
  label: string
  rows: SavedImageQueueSnapshot['pending']
  tone: 'active' | 'pending' | 'failed' | 'completed'
}) {
  const toneClass = {
    active: 'text-blue-600',
    pending: 'text-muted-foreground',
    failed: 'text-destructive',
    completed: 'text-muted-foreground',
  }[tone]
  return (
    <div className="space-y-1">
      <p className={`text-xs font-medium uppercase tracking-wide ${toneClass}`}>
        {label} ({rows.length})
      </p>
      <ul className="space-y-1">
        {rows.map(r => (
          <li
            key={r.id}
            className="flex items-center justify-between text-sm py-1 border-b last:border-b-0 gap-2"
          >
            <span className="truncate font-mono text-xs">
              {r.channel_slug ? (
                <Link
                  to={`/article/${r.channel_slug}/${r.article_id}`}
                  className="hover:underline"
                >
                  글 #{r.article_id}
                </Link>
              ) : (
                <>글 #{r.article_id}</>
              )}
              <span className="text-muted-foreground ml-2">{r.hex.slice(0, 8)}</span>
            </span>
            <span className="text-xs text-muted-foreground shrink-0 truncate max-w-[50%]">
              {tone === 'failed' && r.error
                ? `${r.retry_count}회 실패: ${r.error}`
                : tone === 'pending' && r.retry_count > 0
                ? `재시도 ${r.retry_count}/3`
                : tone === 'completed' && r.completed_at
                ? new Date(r.completed_at).toLocaleTimeString('ko-KR')
                : ''}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
