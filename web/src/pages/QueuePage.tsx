import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
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
    </div>
  )
}
