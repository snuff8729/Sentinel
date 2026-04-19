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
  backupStatuses?: Record<string, { status: string; group_name: string | null; group_id: number | null }>
  onSearchAuthor?: (author: string) => void
  followedUsers?: Set<string>
  onToggleFollow?: (username: string) => void
  updateCandidates?: Record<number, { matched_title: string; group_name: string | null; reason: string }>
}

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  completed: { label: '완료', className: 'bg-green-100 text-green-700 border-green-300' },
  failed: { label: '실패', className: 'bg-red-100 text-red-700 border-red-300' },
  in_progress: { label: '진행중', className: 'bg-blue-100 text-blue-700 border-blue-300 animate-pulse' },
  pending: { label: '대기', className: 'bg-yellow-100 text-yellow-700 border-yellow-300' },
  cancelled: { label: '취소', className: 'bg-gray-100 text-gray-500 border-gray-300' },
}

export function ArticleList({
  slug, articles, selected, onToggle, onToggleAll,
  backupStatuses = {}, onSearchAuthor, followedUsers = new Set(), onToggleFollow,
  updateCandidates = {},
}: Props) {
  const allSelected = articles.length > 0 && articles.every(a => selected.has(a.id))

  return (
    <div className="space-y-0 border rounded-md">
      {/* 전체 선택 헤더 */}
      <div className="flex items-center gap-3 px-3 py-2 border-b bg-muted/50">
        <Checkbox checked={allSelected} onCheckedChange={onToggleAll} />
        <span className="text-xs text-muted-foreground">전체 선택</span>
      </div>

      {articles.map((article) => {
        const backupInfo = backupStatuses[String(article.id)]
        const status = backupInfo?.status
        const badgeInfo = status ? STATUS_BADGE[status] : null
        const groupName = backupInfo?.group_name
        const isFollowed = followedUsers.has(article.author)
        const update = updateCandidates[article.id]
        const isQueued = status === 'completed' || status === 'in_progress' || status === 'pending'

        return (
          <div
            key={article.id}
            className={`flex items-start gap-3 px-3 py-2.5 border-b last:border-b-0 hover:bg-muted/30 ${
              isFollowed ? 'bg-amber-50/50' : ''
            }`}
          >
            <div className="pt-0.5">
              <Checkbox
                checked={selected.has(article.id)}
                onCheckedChange={() => !isQueued && onToggle(article.id)}
                disabled={isQueued}
              />
            </div>
            <div className="flex-1 min-w-0 relative group/title">
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
                {update ? (
                  <span
                    className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border mr-1.5 align-middle bg-orange-100 text-orange-700 border-orange-300"
                    title={`${update.reason} — 기존: ${update.matched_title}`}
                  >
                    🔄 {update.group_name || '업데이트'}
                  </span>
                ) : groupName ? (
                  <span
                    className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border mr-1.5 align-middle bg-purple-100 text-purple-700 border-purple-300"
                  >
                    📦 {groupName}
                  </span>
                ) : null}
                {article.category && (
                  <Badge variant="secondary" className="mr-1.5 text-xs align-middle">
                    {article.category}
                  </Badge>
                )}
                <span className="align-middle">{article.title}</span>
                {article.comment_count > 0 && (
                  <span className="text-blue-500 ml-1 text-xs align-middle">[{article.comment_count}]</span>
                )}
                {article.has_image && <span className="ml-1 text-blue-400 text-xs align-middle" title="이미지">🖼</span>}
                {article.has_video && <span className="ml-1 text-blue-400 text-xs align-middle" title="비디오">🎬</span>}
              </Link>

              {/* 썸네일 hover 프리뷰 */}
              {article.thumbnail_url && (
                <div className="hidden group-hover/title:block absolute left-0 top-full mt-1 z-40 p-1 bg-popover border rounded shadow-lg pointer-events-none">
                  <img
                    src={article.thumbnail_url}
                    alt=""
                    loading="lazy"
                    referrerPolicy="no-referrer"
                    className="block max-w-[320px] max-h-[320px] object-contain rounded"
                  />
                </div>
              )}

              {/* 아랫줄: ★ + 팔로우 + 작성자 + 날짜 + 조회 + 추천 */}
              <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                {article.is_best && (
                  <span className="text-yellow-500">★</span>
                )}
                {isFollowed && (
                  <span className="text-amber-500 text-[10px]">♥</span>
                )}
                <button
                  className={`hover:underline ${isFollowed ? 'text-amber-600 font-medium' : 'hover:text-foreground'}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSearchAuthor?.(article.author)
                  }}
                >
                  {article.author}
                </button>
                <button
                  className={`text-[10px] px-1 py-0 rounded border transition-colors ${
                    isFollowed
                      ? 'border-amber-300 bg-amber-100 text-amber-600 hover:bg-amber-200'
                      : 'border-gray-300 text-gray-400 hover:bg-gray-100 hover:text-gray-600'
                  }`}
                  onClick={(e) => {
                    e.stopPropagation()
                    if (article.author) onToggleFollow?.(article.author)
                  }}
                  disabled={!article.author}
                  title={isFollowed ? '팔로우 해제' : '팔로우'}
                >
                  {isFollowed ? '팔로잉' : '+'}
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
