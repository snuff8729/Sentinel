import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'
import { versionApi } from '@/api/client'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import type { VersionGroupDetail } from '@/api/types'

const STATUS_DOT: Record<string, string> = {
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  pending: 'bg-yellow-500',
  in_progress: 'bg-blue-500',
}

export function VersionsPage() {
  const [groups, setGroups] = useState<VersionGroupDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [movingArticle, setMovingArticle] = useState<{ articleId: number; fromGroupId: number } | null>(null)
  const [moveSearch, setMoveSearch] = useState('')

  const load = () => {
    setLoading(true)
    versionApi.listGroups().then(setGroups).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleRename = async (groupId: number) => {
    if (!editName.trim()) return
    await versionApi.renameGroup(groupId, editName.trim())
    setEditingId(null)
    load()
  }

  const handleDelete = async (groupId: number) => {
    await versionApi.deleteGroup(groupId)
    toast.success('그룹이 삭제되었습니다.')
    load()
  }

  const filtered = search
    ? groups.filter(g =>
        g.name.toLowerCase().includes(search.toLowerCase()) ||
        g.articles.some(a => a.title.toLowerCase().includes(search.toLowerCase()))
      )
    : groups

  if (loading) return <div className="text-center py-8 text-muted-foreground">로딩 중...</div>

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">버전 관리</h1>
        <span className="text-sm text-muted-foreground">{groups.length}개 그룹</span>
      </div>

      <Input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="그룹명 또는 게시글 제목 검색..."
        className="max-w-sm"
      />

      {filtered.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          {search ? '검색 결과가 없습니다.' : '버전 그룹이 없습니다. 게시글을 백업하면 자동으로 생성됩니다.'}
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(group => (
            <div key={group.id} className="border rounded-md">
              {/* 그룹 헤더 */}
              <div className="flex items-center gap-3 px-4 py-3 bg-muted/30 border-b">
                <div className="flex-1 min-w-0">
                  {editingId === group.id ? (
                    <div className="flex gap-2">
                      <Input
                        value={editName}
                        onChange={e => setEditName(e.target.value)}
                        className="h-7 text-sm"
                        onKeyDown={e => e.key === 'Enter' && handleRename(group.id)}
                        autoFocus
                      />
                      <Button size="sm" className="h-7" onClick={() => handleRename(group.id)}>저장</Button>
                      <Button size="sm" variant="ghost" className="h-7" onClick={() => setEditingId(null)}>취소</Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{group.name}</span>
                      {group.author && <span className="text-xs text-muted-foreground">by {group.author}</span>}
                      <span className="text-xs text-muted-foreground">({group.articles.length}개)</span>
                    </div>
                  )}
                </div>
                {editingId !== group.id && (
                  <div className="flex gap-1">
                    <Button
                      size="sm" variant="ghost" className="h-7 text-xs"
                      onClick={() => { setEditingId(group.id); setEditName(group.name) }}
                    >
                      이름 수정
                    </Button>
                    <ConfirmDialog
                      trigger={
                        <Button size="sm" variant="ghost" className="h-7 text-xs text-destructive">삭제</Button>
                      }
                      title="그룹 삭제"
                      description={`"${group.name}" 그룹을 삭제할까요? 게시글은 유지됩니다.`}
                      onConfirm={() => handleDelete(group.id)}
                      confirmText="삭제"
                    />
                  </div>
                )}
              </div>

              {/* 게시글 목록 */}
              {group.articles.map(article => (
                <div key={article.id} className="flex items-center gap-3 px-4 py-2 border-b last:border-b-0 hover:bg-muted/20">
                  <span className={`w-2 h-2 rounded-full ${STATUS_DOT[article.backup_status] ?? 'bg-gray-300'}`} />
                  <div className="flex-1 min-w-0">
                    <Link to={`/backup/${article.id}`} className="text-sm hover:underline truncate block">
                      {article.title}
                    </Link>
                    <div className="text-xs text-muted-foreground">
                      {article.version_label && <span className="mr-2 font-medium">{article.version_label}</span>}
                      {article.author}
                      {article.created_at && ` · ${new Date(article.created_at).toLocaleDateString('ko-KR')}`}
                    </div>
                  </div>
                  <Button
                    size="sm" variant="ghost" className="h-6 text-xs text-muted-foreground"
                    onClick={() => {
                      setMovingArticle({ articleId: article.id, fromGroupId: group.id })
                      setMoveSearch('')
                    }}
                  >
                    이동
                  </Button>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* 이동 모달 */}
      {movingArticle && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setMovingArticle(null)}>
          <div className="bg-background border rounded-md shadow-lg w-96 max-h-96 flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="p-3 border-b">
              <p className="text-sm font-medium mb-2">이동할 그룹 선택</p>
              <Input
                value={moveSearch}
                onChange={e => setMoveSearch(e.target.value)}
                placeholder="그룹 검색 또는 새 그룹명..."
                autoFocus
              />
            </div>
            <div className="flex-1 overflow-y-auto">
              {/* 새 그룹 생성 */}
              {moveSearch.trim() && !groups.some(g => g.name === moveSearch.trim()) && (
                <button
                  className="w-full text-left px-3 py-2 text-sm hover:bg-muted border-b flex items-center gap-2"
                  onClick={async () => {
                    const newGroup = await versionApi.createGroup(moveSearch.trim())
                    await versionApi.addArticle(newGroup.id, movingArticle.articleId)
                    setMovingArticle(null)
                    load()
                  }}
                >
                  <span className="text-blue-500 text-xs font-medium">+ 새 그룹</span>
                  <span className="font-medium">"{moveSearch.trim()}"</span>
                </button>
              )}
              {/* 기존 그룹 */}
              {groups
                .filter(g => g.id !== movingArticle.fromGroupId)
                .filter(g => !moveSearch.trim() || g.name.toLowerCase().includes(moveSearch.toLowerCase()))
                .map(g => (
                  <button
                    key={g.id}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-muted border-b last:border-b-0"
                    onClick={async () => {
                      await versionApi.addArticle(g.id, movingArticle.articleId)
                      setMovingArticle(null)
                      load()
                    }}
                  >
                    <span className="font-medium">{g.name}</span>
                    {g.author && <span className="text-muted-foreground ml-2">by {g.author}</span>}
                    <span className="text-muted-foreground ml-2">({g.articles.length}개)</span>
                  </button>
                ))}
            </div>
            <div className="p-2 border-t">
              <Button size="sm" variant="ghost" className="w-full" onClick={() => setMovingArticle(null)}>취소</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
