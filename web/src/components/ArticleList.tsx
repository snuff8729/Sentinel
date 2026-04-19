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
  onSearchAuthor?: (author: string) => void
}

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  completed: { label: '완료', className: 'bg-green-100 text-green-700 border-green-300' },
  failed: { label: '실패', className: 'bg-red-100 text-red-700 border-red-300' },
  in_progress: { label: '진행중', className: 'bg-blue-100 text-blue-700 border-blue-300 animate-pulse' },
  pending: { label: '대기', className: 'bg-yellow-100 text-yellow-700 border-yellow-300' },
  cancelled: { label: '취소', className: 'bg-gray-100 text-gray-500 border-gray-300' },
}

export function ArticleList({ slug, articles, selected, onToggle, onToggleAll, backupStatuses = {}, onSearchAuthor }: Props) {
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
        const badgeInfo = status ? STATUS_BADGE[status] : null

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
                {badgeInfo && (
                  <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border mr-1.5 align-middle ${badgeInfo.className}`}>
                    {badgeInfo.label}
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
                <button
                  className="hover:underline hover:text-foreground"
                  onClick={(e) => {
                    e.stopPropagation()
                    onSearchAuthor?.(article.author)
                  }}
                >
                  {article.author}
                </button>
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
