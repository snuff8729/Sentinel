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
      <div className="flex gap-2">
        {paused ? (
          <Button onClick={onResume}>재개</Button>
        ) : (
          <Button variant="outline" onClick={onPause}>일시정지</Button>
        )}
      </div>

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
