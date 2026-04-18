import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CommentList } from '@/components/CommentList'
import { articleApi, backupApi } from '@/api/client'
import type { ArticleDetail, Comment } from '@/api/types'

export function ArticleDetailPage() {
  const { slug, id } = useParams<{ slug: string; id: string }>()
  const [detail, setDetail] = useState<ArticleDetail | null>(null)
  const [comments, setComments] = useState<Comment[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!slug || !id) return
    const articleId = Number(id)
    setLoading(true)
    Promise.all([
      articleApi.getDetail(slug, articleId),
      articleApi.getComments(slug, articleId),
    ]).then(([d, c]) => {
      setDetail(d)
      setComments(c)
    }).finally(() => setLoading(false))
  }, [slug, id])

  const handleBackup = async () => {
    if (!slug || !id) return
    await backupApi.enqueue(slug, Number(id))
    alert('백업 큐에 추가했습니다.')
  }

  if (loading) return <div className="text-center py-8 text-muted-foreground">로딩 중...</div>
  if (!detail) return <div className="text-center py-8">게시글을 찾을 수 없습니다.</div>

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          {detail.category && <Badge variant="secondary">{detail.category}</Badge>}
          <h1 className="text-2xl font-bold">{detail.title}</h1>
        </div>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{detail.author}</span>
          <span>{new Date(detail.created_at).toLocaleString('ko-KR')}</span>
          <span>조회 {detail.view_count}</span>
          <span>추천 {detail.vote_count}</span>
          <span>비추 {detail.down_vote_count}</span>
        </div>
      </div>

      <Button onClick={handleBackup}>이 글 백업</Button>

      <div
        className="prose prose-sm max-w-none border-t pt-4"
        dangerouslySetInnerHTML={{ __html: detail.content_html }}
      />

      <div className="border-t pt-4">
        <CommentList comments={comments} />
      </div>
    </div>
  )
}
