import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { versionApi } from '@/api/client'
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

  const handleDelete = async (groupId: number, name: string) => {
    if (!confirm(`"${name}" 그룹을 삭제할까요? 게시글은 유지됩니다.`)) return
    await versionApi.deleteGroup(groupId)
    load()
  }

  const handleRemoveArticle = async (groupId: number, articleId: number) => {
    await versionApi.removeArticle(groupId, articleId)
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
                    <Button
                      size="sm" variant="ghost" className="h-7 text-xs text-destructive"
                      onClick={() => handleDelete(group.id, group.name)}
                    >
                      삭제
                    </Button>
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
                  {group.articles.length > 1 && (
                    <Button
                      size="sm" variant="ghost" className="h-6 text-xs text-muted-foreground"
                      onClick={() => handleRemoveArticle(group.id, article.id)}
                    >
                      분리
                    </Button>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
