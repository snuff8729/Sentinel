import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import type { ArticleRow } from '@/api/types'

interface Props {
  slug: string
  articles: ArticleRow[]
  selected: Set<number>
  onToggle: (id: number) => void
  onToggleAll: () => void
  backupStatuses?: Record<string, string>
}

const STATUS_ICON: Record<string, { icon: string; color: string }> = {
  completed: { icon: '✓', color: 'text-green-500' },
  failed: { icon: '✗', color: 'text-red-500' },
  in_progress: { icon: '↻', color: 'text-blue-500' },
  pending: { icon: '⏳', color: 'text-yellow-500' },
  cancelled: { icon: '—', color: 'text-muted-foreground' },
}

export function ArticleList({ slug, articles, selected, onToggle, onToggleAll, backupStatuses = {} }: Props) {
  const allSelected = articles.length > 0 && articles.every(a => selected.has(a.id))

  return (
    <div className="space-y-0 border rounded-md">
      {/* 전체 선택 헤더 */}
      <div className="flex items-center gap-3 px-3 py-2 border-b bg-muted/50">
        <Checkbox checked={allSelected} onCheckedChange={onToggleAll} />
        <span className="text-xs text-muted-foreground">전체 선택</span>
      </div>

      {articles.map((article) => {
        const status = backupStatuses[String(article.id)]
        const statusInfo = status ? STATUS_ICON[status] : null

        return (
          <div key={article.id} className="flex items-start gap-3 px-3 py-2.5 border-b last:border-b-0 hover:bg-muted/30">
            <div className="pt-0.5">
              <Checkbox
                checked={selected.has(article.id)}
                onCheckedChange={() => onToggle(article.id)}
              />
            </div>
            <div className="flex-1 min-w-0">
              {/* 윗줄: 백업상태 + 카테고리 + 제목 + 댓글수 */}
              <Link
                to={`/article/${slug}/${article.id}`}
                className="hover:underline leading-snug"
              >
                {statusInfo && (
                  <span className={`${statusInfo.color} mr-1 align-middle`} title={status}>
                    {statusInfo.icon}
                  </span>
                )}
                {article.category && (
                  <Badge variant="secondary" className="mr-1.5 text-xs align-middle">
                    {article.category}
                  </Badge>
                )}
                <span className="align-middle">{article.title}</span>
                {article.comment_count > 0 && (
                  <span className="text-blue-500 ml-1 text-xs align-middle">[{article.comment_count}]</span>
                )}
              </Link>

              {/* 아랫줄: ★ + 작성자 + 날짜 + 조회 + 추천 */}
              <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                {article.is_best && (
                  <span className="text-yellow-500">★</span>
                )}
                <span>{article.author}</span>
                <span>·</span>
                <span>{new Date(article.created_at).toLocaleDateString('ko-KR')}</span>
                <span>·</span>
                <span>조회 {article.view_count}</span>
                <span>·</span>
                <span>추천 {article.vote_count}</span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
