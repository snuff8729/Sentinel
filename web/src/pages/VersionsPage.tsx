import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from 'sonner'
import { versionApi } from '@/api/client'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import type { VersionGroupDetail, VersionGroupSummary } from '@/api/types'

const STATUS_DOT: Record<string, string> = {
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  pending: 'bg-yellow-500',
  in_progress: 'bg-blue-500',
}

type SortKey = 'latest' | 'name' | 'count' | 'author'
type SortDir = 'asc' | 'desc'

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'latest', label: '최근 업데이트' },
  { value: 'count', label: '게시글 수' },
  { value: 'name', label: '그룹명' },
  { value: 'author', label: '작성자' },
]

const PAGE_SIZE = 50

export function VersionsPage() {
  const [items, setItems] = useState<VersionGroupSummary[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const [searchParams, setSearchParams] = useSearchParams()
  const page = parseInt(searchParams.get('page') ?? '1', 10) || 1
  const sortKey = (searchParams.get('sort') as SortKey | null) ?? 'latest'
  const sortDir = (searchParams.get('dir') as SortDir | null) ?? 'desc'
  const searchParam = searchParams.get('q') ?? ''
  const [searchInput, setSearchInput] = useState(searchParam)

  const updateParams = (next: { sort?: SortKey; dir?: SortDir; page?: number; q?: string }) => {
    const params: Record<string, string> = {}
    const s = next.sort !== undefined ? next.sort : sortKey
    const d = next.dir !== undefined ? next.dir : sortDir
    const p = next.page !== undefined ? next.page : page
    const q = next.q !== undefined ? next.q : searchParam
    if (s && s !== 'latest') params.sort = s
    if (d && d !== 'desc') params.dir = d
    if (p && p !== 1) params.page = String(p)
    if (q) params.q = q
    setSearchParams(params)
  }

  // 검색어 debounce — 입력 300ms 후 URL 갱신
  useEffect(() => {
    if (searchInput === searchParam) return
    const timer = window.setTimeout(() => {
      updateParams({ q: searchInput, page: 1 })
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchInput]) // eslint-disable-line react-hooks/exhaustive-deps

  // 펼침 상태 + lazy-loaded 게시글 상세
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [expandedGroup, setExpandedGroup] = useState<VersionGroupDetail | null>(null)
  const [expandLoading, setExpandLoading] = useState(false)

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [movingArticle, setMovingArticle] = useState<{ articleId: number; fromGroupId: number } | null>(null)
  const [moveSearch, setMoveSearch] = useState('')
  const [moveResults, setMoveResults] = useState<{ id: number; name: string; author: string | null; article_count: number }[]>([])

  const load = useCallback(() => {
    setLoading(true)
    versionApi.listGroups({ page, size: PAGE_SIZE, sort: sortKey, dir: sortDir, search: searchParam || undefined })
      .then(res => {
        setItems(res.items)
        setTotal(res.total)
      })
      .finally(() => setLoading(false))
  }, [page, sortKey, sortDir, searchParam])

  useEffect(() => { load() }, [load])

  const handleExpand = async (groupId: number) => {
    if (expandedId === groupId) {
      setExpandedId(null)
      setExpandedGroup(null)
      return
    }
    setExpandedId(groupId)
    setExpandedGroup(null)
    setExpandLoading(true)
    try {
      const detail = await versionApi.getGroup(groupId)
      setExpandedGroup(detail)
    } finally {
      setExpandLoading(false)
    }
  }

  const handleRename = async (groupId: number) => {
    if (!editName.trim()) return
    await versionApi.renameGroup(groupId, editName.trim())
    setEditingId(null)
    load()
    if (expandedId === groupId) {
      versionApi.getGroup(groupId).then(setExpandedGroup)
    }
  }

  const handleDelete = async (groupId: number) => {
    await versionApi.deleteGroup(groupId)
    toast.success('그룹이 삭제되었습니다.')
    if (expandedId === groupId) {
      setExpandedId(null)
      setExpandedGroup(null)
    }
    load()
  }

  // 이동 모달의 그룹 검색 (별도 API)
  useEffect(() => {
    if (!movingArticle) return
    const kw = moveSearch.trim()
    if (!kw) { setMoveResults([]); return }
    const timer = window.setTimeout(() => {
      versionApi.searchGroups(kw).then(r => {
        setMoveResults(r.filter(g => g.id !== movingArticle.fromGroupId))
      }).catch(() => setMoveResults([]))
    }, 200)
    return () => window.clearTimeout(timer)
  }, [moveSearch, movingArticle])

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">버전 관리</h1>
        <span className="text-sm text-muted-foreground">{total}개 그룹</span>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <Input
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          placeholder="그룹명 또는 게시글 제목 검색..."
          className="max-w-sm"
        />
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">정렬</span>
          <Select value={sortKey} onValueChange={(v) => v && updateParams({ sort: v as SortKey, page: 1 })}>
            <SelectTrigger className="w-36 h-8 text-xs">
              <SelectValue>
                {(v) => SORT_OPTIONS.find(o => o.value === v)?.label ?? v}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map(opt => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => updateParams({ dir: sortDir === 'desc' ? 'asc' : 'desc', page: 1 })}
            title={sortDir === 'desc' ? '내림차순' : '오름차순'}
          >
            {sortDir === 'desc' ? '↓' : '↑'}
          </Button>
        </div>
      </div>

      {loading && items.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">로딩 중...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          {searchParam ? '검색 결과가 없습니다.' : '버전 그룹이 없습니다. 게시글을 백업하면 자동으로 생성됩니다.'}
        </div>
      ) : (
        <div className="border rounded-md">
          {items.map(group => {
            const isExpanded = expandedId === group.id
            const isEditing = editingId === group.id
            return (
              <div key={group.id} className="border-b last:border-b-0">
                {/* 그룹 행 (클릭하여 펼침) */}
                <div
                  className={`flex items-start gap-3 px-4 py-2.5 cursor-pointer hover:bg-muted/20 ${isExpanded ? 'bg-muted/10' : ''}`}
                  onClick={() => !isEditing && handleExpand(group.id)}
                >
                  <span className="text-muted-foreground text-xs pt-1">
                    {isExpanded ? '▼' : '▶'}
                  </span>
                  <div className="flex-1 min-w-0">
                    {isEditing ? (
                      <div className="flex gap-2" onClick={e => e.stopPropagation()}>
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
                      <div className="leading-snug">
                        <span className="font-medium align-middle">{group.name}</span>
                        {group.author && <span className="text-xs text-muted-foreground ml-2 align-middle">by {group.author}</span>}
                        <span className="text-xs text-muted-foreground ml-2 align-middle">({group.article_count}개)</span>
                        {group.latest_at && (
                          <span className="text-xs text-muted-foreground ml-2 align-middle">
                            최근 {new Date(group.latest_at).toLocaleDateString('ko-KR')}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  {!isEditing && (
                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                      <Button
                        size="sm" variant="ghost" className="h-7 text-xs"
                        onClick={() => { setEditingId(group.id); setEditName(group.name) }}
                      >
                        이름 수정
                      </Button>
                      <span onClick={e => e.stopPropagation()}>
                        <ConfirmDialog
                          trigger={
                            <Button size="sm" variant="ghost" className="h-7 text-xs text-destructive">삭제</Button>
                          }
                          title="그룹 삭제"
                          description={`"${group.name}" 그룹을 삭제할까요? 게시글은 유지됩니다.`}
                          onConfirm={() => handleDelete(group.id)}
                          confirmText="삭제"
                        />
                      </span>
                    </div>
                  )}
                </div>

                {/* 펼침: 그룹에 속한 게시글 목록 (lazy fetch) */}
                {isExpanded && (
                  <div className="bg-muted/30 border-t">
                    {expandLoading || !expandedGroup ? (
                      <div className="px-4 py-3 text-sm text-muted-foreground">로딩 중...</div>
                    ) : expandedGroup.articles.length === 0 ? (
                      <div className="px-4 py-3 text-sm text-muted-foreground">게시글이 없습니다.</div>
                    ) : (
                      expandedGroup.articles.map(article => (
                        <div key={article.id} className="flex items-center gap-3 px-4 py-2 border-b last:border-b-0 hover:bg-muted/50 text-sm">
                          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[article.backup_status] ?? 'bg-gray-300'}`} />
                          <div className="flex-1 min-w-0">
                            <Link to={`/backup/${article.id}`} className="hover:underline truncate block">
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
                              setMoveResults([])
                            }}
                          >
                            이동
                          </Button>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* 페이지네이션 */}
      {pageCount > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} / {total}
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm" variant="outline"
              disabled={page <= 1}
              onClick={() => updateParams({ page: page - 1 })}
            >
              이전
            </Button>
            <span className="px-2">{page} / {pageCount}</span>
            <Button
              size="sm" variant="outline"
              disabled={page >= pageCount}
              onClick={() => updateParams({ page: page + 1 })}
            >
              다음
            </Button>
          </div>
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
              {moveSearch.trim() && !moveResults.some(g => g.name === moveSearch.trim()) && (
                <button
                  className="w-full text-left px-3 py-2 text-sm hover:bg-muted border-b flex items-center gap-2"
                  onClick={async () => {
                    const newGroup = await versionApi.createGroup(moveSearch.trim())
                    await versionApi.addArticle(newGroup.id, movingArticle.articleId)
                    setMovingArticle(null)
                    load()
                    if (expandedId) versionApi.getGroup(expandedId).then(setExpandedGroup)
                  }}
                >
                  <span className="text-blue-500 text-xs font-medium">+ 새 그룹</span>
                  <span className="font-medium">"{moveSearch.trim()}"</span>
                </button>
              )}
              {/* 기존 그룹 */}
              {moveResults.map(g => (
                <button
                  key={g.id}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-muted border-b last:border-b-0"
                  onClick={async () => {
                    await versionApi.addArticle(g.id, movingArticle.articleId)
                    setMovingArticle(null)
                    load()
                    if (expandedId) versionApi.getGroup(expandedId).then(setExpandedGroup)
                  }}
                >
                  <span className="font-medium">{g.name}</span>
                  {g.author && <span className="text-muted-foreground ml-2">by {g.author}</span>}
                  <span className="text-muted-foreground ml-2">({g.article_count}개)</span>
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
