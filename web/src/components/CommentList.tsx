import type { Comment } from '@/api/types'

function CommentItem({ comment, isReply = false }: { comment: Comment; isReply?: boolean }) {
  return (
    <div className={`py-3 ${isReply ? 'ml-8 border-l-2 pl-4' : 'border-b'}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="font-medium text-sm">{comment.author}</span>
        <span className="text-xs text-muted-foreground">
          {new Date(comment.created_at).toLocaleString('ko-KR')}
        </span>
      </div>
      <div
        className="text-sm prose prose-sm max-w-none"
        dangerouslySetInnerHTML={{ __html: comment.content_html }}
      />
      {comment.replies.map(reply => (
        <CommentItem key={reply.id} comment={reply} isReply />
      ))}
    </div>
  )
}

export function CommentList({ comments }: { comments: Comment[] }) {
  return (
    <div>
      <h3 className="font-bold mb-2">댓글 ({comments.length})</h3>
      {comments.map(c => (
        <CommentItem key={c.id} comment={c} />
      ))}
    </div>
  )
}
