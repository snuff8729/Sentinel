import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { articleApi, backupApi, channelApi, versionApi } from '@/api/client'
import type { ChannelInfo } from '@/api/types'
import { Input } from '@/components/ui/input'
import type { ArticleDetail } from '@/api/types'
import { attachSaveButtons } from '@/lib/saveImageButton'
import '@/styles/article-content.css'

export function ArticleDetailPage() {
  const { slug, id } = useParams<{ slug: string; id: string }>()
  const [detail, setDetail] = useState<ArticleDetail | null>(null)
  const [commentsHtml, setCommentsHtml] = useState('')
  const [loading, setLoading] = useState(true)
  const [showVersionPicker, setShowVersionPicker] = useState(false)
  const [versionSearch, setVersionSearch] = useState('')
  const [versionResults, setVersionResults] = useState<{ id: number; name: string; author: string | null; article_count: number }[]>([])
  const [selectedGroup, setSelectedGroup] = useState<{ id: number; name: string } | 'new' | null>(null)
  const [backupQueued, setBackupQueued] = useState(false)
  const [backupStatus, setBackupStatus] = useState<string | null>(null)
  const [versionGroup, setVersionGroup] = useState<{ id: number; name: string; articles: { id: number; title: string; version_label: string | null; backup_status: string; created_at: string | null }[] } | null>(null)
  const [channelInfo, setChannelInfo] = useState<ChannelInfo | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!slug || !id) return
    const articleId = Number(id)
    setLoading(true)
    setBackupStatus(null)
    Promise.all([
      articleApi.getDetail(slug, articleId),
      articleApi.getComments(slug, articleId),
    ]).then(([d, c]) => {
      setDetail(d)
      setCommentsHtml(c.html)
    }).finally(() => setLoading(false))
    // 채널 정보
    channelApi.getInfo(slug).then(setChannelInfo).catch(() => {})
    // 백업 상태 + 버전 그룹 확인
    backupApi.getStatuses([articleId]).then(statuses => {
      setBackupStatus(statuses[String(articleId)]?.status || null)
    })
    backupApi.getDetail(articleId).then(detail => {
      if (detail.article?.version_group_id) {
        versionApi.getGroup(detail.article.version_group_id).then(setVersionGroup).catch(() => {})
      } else {
        setVersionGroup(null)
      }
    }).catch(() => setVersionGroup(null))
  }, [slug, id])

  const handleSearchVersions = async (keyword: string) => {
    setVersionSearch(keyword)
    if (keyword.trim().length < 1) { setVersionResults([]); return }
    const results = await versionApi.searchGroups(keyword)
    setVersionResults(results)
  }

  const bodyDanger = useMemo(
    () => ({ __html: detail?.content_html ?? '' }),
    [detail?.content_html]
  )

  useEffect(() => {
    if (!detail || !contentRef.current) return
    return attachSaveButtons(contentRef.current, detail.id)
  }, [detail?.id])

  if (loading) return <div className="text-center py-8 text-muted-foreground">로딩 중...</div>
  if (!detail) return <div className="text-center py-8">게시글을 찾을 수 없습니다.</div>

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* 채널 */}
      {channelInfo && slug && (
        <Link to={`/channel/${slug}`} className="flex items-center gap-2 hover:opacity-80">
          {channelInfo.icon_url && (
            <img src={channelInfo.icon_url} alt="" className="w-6 h-6 rounded" referrerPolicy="no-referrer" />
          )}
          <span className="text-sm text-muted-foreground">{channelInfo.name}</span>
        </Link>
      )}

      {/* 헤더 */}
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

      {/* 액션 */}
      <div className="space-y-3">
        <div className="flex gap-2 items-center">
          {backupStatus === 'completed' || backupStatus === 'pending' || backupStatus === 'in_progress' ? (
            <>
              <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium border ${
                backupStatus === 'completed' ? 'bg-green-100 text-green-700 border-green-300' :
                backupStatus === 'in_progress' ? 'bg-blue-100 text-blue-700 border-blue-300 animate-pulse' :
                'bg-yellow-100 text-yellow-700 border-yellow-300'
              }`}>
                {backupStatus === 'completed' ? '백업 완료' : backupStatus === 'in_progress' ? '백업 중' : '대기 중'}
              </span>
              <Link to={`/backup/${id}`}>
                <Button size="sm" variant="outline">백업 보기</Button>
              </Link>
              <Button
                size="sm"
                variant="outline"
                onClick={() => { setShowVersionPicker(!showVersionPicker); setBackupQueued(false) }}
              >
                다시 백업
              </Button>
            </>
          ) : backupStatus === 'failed' ? (
            <>
              <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium border bg-red-100 text-red-700 border-red-300">
                백업 실패
              </span>
              <Button onClick={() => { setShowVersionPicker(!showVersionPicker); setBackupQueued(false) }}>
                재시도
              </Button>
            </>
          ) : (
            <Button onClick={() => { setShowVersionPicker(!showVersionPicker); setBackupQueued(false) }}>
              이 글 백업
            </Button>
          )}
        </div>

        {/* 큐 추가 피드백 */}
        {backupQueued && (
          <div className="text-sm p-3 rounded border bg-green-50 border-green-200 text-green-700">
            백업 큐에 추가되었습니다.
          </div>
        )}

        {/* 버전 연결 + 백업 패널 */}
        {showVersionPicker && (
          <div className="border rounded-md p-4 space-y-3 bg-muted/10">
            <p className="text-sm font-medium">버전 그룹 선택</p>
            <Input
              value={versionSearch}
              onChange={e => handleSearchVersions(e.target.value)}
              placeholder="그룹 검색 또는 새 그룹명 입력..."
              autoFocus
            />

            <div className="max-h-48 overflow-y-auto border rounded">
              {/* 기본: 새 그룹으로 (제목 자동) */}
              <button
                className={`w-full text-left px-3 py-2 text-sm border-b ${selectedGroup === 'new' && !versionSearch.trim() ? 'bg-blue-50' : 'hover:bg-muted'}`}
                onClick={() => { setSelectedGroup('new'); setVersionSearch('') }}
              >
                <span className="text-muted-foreground">새 그룹으로 백업</span>
                <span className="text-xs text-muted-foreground ml-1">(제목으로 자동 생성)</span>
              </button>

              {/* 검색어로 새 그룹 생성 */}
              {versionSearch.trim() && !versionResults.some(g => g.name === versionSearch.trim()) && (
                <button
                  className={`w-full text-left px-3 py-2 text-sm border-b flex items-center gap-2 ${
                    selectedGroup === 'new' && versionSearch.trim() ? 'bg-blue-50' : 'hover:bg-muted'
                  }`}
                  onClick={() => setSelectedGroup('new')}
                >
                  <span className="text-blue-500 text-xs font-medium">+ 새 그룹</span>
                  <span className="font-medium">"{versionSearch.trim()}"</span>
                </button>
              )}

              {/* 기존 그룹 */}
              {versionResults.map(g => (
                <button
                  key={g.id}
                  className={`w-full text-left px-3 py-2 text-sm border-b last:border-b-0 ${
                    selectedGroup && selectedGroup !== 'new' && selectedGroup.id === g.id ? 'bg-blue-50' : 'hover:bg-muted'
                  }`}
                  onClick={() => setSelectedGroup({ id: g.id, name: g.name })}
                >
                  <span className="font-medium">{g.name}</span>
                  {g.author && <span className="text-muted-foreground ml-2">by {g.author}</span>}
                  <span className="text-muted-foreground ml-2">({g.article_count}개)</span>
                </button>
              ))}
            </div>

            {/* 선택 확인 + 백업 시작 */}
            <div className="flex items-center gap-3 pt-1">
              <div className="flex-1 text-sm text-muted-foreground">
                {selectedGroup === 'new' && versionSearch.trim()
                  ? `새 그룹 "${versionSearch.trim()}" 생성 후 백업`
                  : selectedGroup === 'new'
                  ? '새 그룹 (제목 자동) 으로 백업'
                  : selectedGroup
                  ? `"${selectedGroup.name}" 그룹에 추가 후 백업`
                  : '그룹을 선택하세요'}
              </div>
              <Button
                size="sm"
                disabled={!selectedGroup}
                onClick={async () => {
                  if (!slug || !id) return
                  const articleId = Number(id)

                  if (selectedGroup === 'new' && versionSearch.trim()) {
                    const group = await versionApi.createGroup(versionSearch.trim(), detail?.author)
                    await backupApi.enqueue(slug, articleId)
                    setTimeout(async () => { try { await versionApi.addArticle(group.id, articleId) } catch {} }, 500)
                  } else if (selectedGroup === 'new') {
                    await backupApi.enqueue(slug, articleId)
                  } else if (selectedGroup) {
                    await backupApi.enqueue(slug, articleId)
                    setTimeout(async () => { try { await versionApi.addArticle(selectedGroup.id, articleId) } catch {} }, 500)
                  }

                  setShowVersionPicker(false)
                  setSelectedGroup(null)
                  setVersionSearch('')
                  setBackupQueued(true)
                  setTimeout(() => setBackupQueued(false), 5000)
                }}
              >
                백업 시작
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setShowVersionPicker(false); setSelectedGroup(null) }}>
                취소
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* 버전 그룹 */}
      {versionGroup && versionGroup.articles.length > 0 && (
        <div className="border rounded-md">
          <div className="px-3 py-2 bg-muted/30 border-b text-sm font-medium flex items-center gap-2">
            <span>📦</span>
            <span>{versionGroup.name}</span>
            <span className="text-xs text-muted-foreground">({versionGroup.articles.length}개)</span>
          </div>
          {versionGroup.articles.map(a => {
            const isCurrent = a.id === Number(id)
            return (
              <div
                key={a.id}
                className={`flex items-center gap-2 px-3 py-1.5 border-b last:border-b-0 text-sm ${isCurrent ? 'bg-blue-50' : 'hover:bg-muted/20'}`}
              >
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  a.backup_status === 'completed' ? 'bg-green-500' :
                  a.backup_status === 'failed' ? 'bg-red-500' : 'bg-gray-300'
                }`} />
                {isCurrent ? (
                  <span className="flex-1 truncate font-medium">{a.title}</span>
                ) : (
                  <Link to={`/article/${slug}/${a.id}`} className="flex-1 truncate hover:underline">
                    {a.title}
                  </Link>
                )}
                {a.version_label && (
                  <span className="text-xs text-muted-foreground">{a.version_label}</span>
                )}
                {isCurrent && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-600 border border-blue-200">현재</span>
                )}
                {a.created_at && (
                  <span className="text-xs text-muted-foreground">{new Date(a.created_at).toLocaleDateString('ko-KR')}</span>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* 본문 */}
      <div
        ref={contentRef}
        className="arca-article-content border-t pt-4"
        dangerouslySetInnerHTML={bodyDanger}
      />

      {/* 댓글 */}
      {commentsHtml && (
        <div
          className="arca-comment-section border-t pt-4"
          dangerouslySetInnerHTML={{ __html: commentsHtml }}
        />
      )}
    </div>
  )
}

