import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { articleApi, backupApi, versionApi } from '@/api/client'
import { Input } from '@/components/ui/input'
import type { AnalyzedLink, ArticleDetail } from '@/api/types'
import '@/styles/article-content.css'

const LINK_TYPE_STYLE: Record<string, { label: string; className: string }> = {
  download: { label: '다운로드', className: 'bg-blue-100 text-blue-700 border-blue-300' },
  reference: { label: '관련 글', className: 'bg-purple-100 text-purple-700 border-purple-300' },
  other: { label: '기타', className: 'bg-gray-100 text-gray-500 border-gray-300' },
}

export function ArticleDetailPage() {
  const { slug, id } = useParams<{ slug: string; id: string }>()
  const [detail, setDetail] = useState<ArticleDetail | null>(null)
  const [commentsHtml, setCommentsHtml] = useState('')
  const [loading, setLoading] = useState(true)
  const [links, setLinks] = useState<AnalyzedLink[]>([])
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState('')
  const [showVersionPicker, setShowVersionPicker] = useState(false)
  const [versionSearch, setVersionSearch] = useState('')
  const [versionResults, setVersionResults] = useState<{ id: number; name: string; author: string | null; article_count: number }[]>([])
  const [selectedGroup, setSelectedGroup] = useState<{ id: number; name: string } | 'new' | null>(null)
  const [backupQueued, setBackupQueued] = useState(false)
  const [backupStatus, setBackupStatus] = useState<string | null>(null)

  useEffect(() => {
    if (!slug || !id) return
    const articleId = Number(id)
    setLoading(true)
    setLinks([])
    setAnalyzeError('')
    setBackupStatus(null)
    Promise.all([
      articleApi.getDetail(slug, articleId),
      articleApi.getComments(slug, articleId),
    ]).then(([d, c]) => {
      setDetail(d)
      setCommentsHtml(c.html)
    }).finally(() => setLoading(false))
    // 백업 상태 확인
    backupApi.getStatuses([articleId]).then(statuses => {
      setBackupStatus(statuses[String(articleId)] || null)
    })
  }, [slug, id])

  const handleSearchVersions = async (keyword: string) => {
    setVersionSearch(keyword)
    if (keyword.trim().length < 1) { setVersionResults([]); return }
    const results = await versionApi.searchGroups(keyword)
    setVersionResults(results)
  }

  const handleAnalyzeLinks = async () => {
    if (!slug || !id) return
    setAnalyzing(true)
    setAnalyzeError('')
    try {
      const result = await articleApi.analyzeLinks(slug, Number(id))
      if (result.error) {
        setAnalyzeError(result.error)
      }
      setLinks(result.links || [])
    } catch (e) {
      setAnalyzeError(String(e))
    } finally {
      setAnalyzing(false)
    }
  }

  if (loading) return <div className="text-center py-8 text-muted-foreground">로딩 중...</div>
  if (!detail) return <div className="text-center py-8">게시글을 찾을 수 없습니다.</div>

  const downloadLinks = links.filter(l => l.type === 'download')
  const referenceLinks = links.filter(l => l.type === 'reference')
  const otherLinks = links.filter(l => l.type === 'other')

  return (
    <div className="max-w-4xl mx-auto space-y-6">
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
          <Button variant="outline" onClick={handleAnalyzeLinks} disabled={analyzing}>
            {analyzing ? '분석 중...' : '링크 분석 (LLM)'}
          </Button>
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

      {/* 분석 에러 */}
      {analyzeError && (
        <div className="text-sm p-3 rounded border bg-red-50 border-red-200 text-red-700">
          {analyzeError}
        </div>
      )}

      {/* 분석된 링크 */}
      {links.length > 0 && (
        <div className="space-y-3 p-4 border rounded-md bg-muted/20">
          <h3 className="font-bold text-sm">분석된 링크</h3>
          {downloadLinks.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-blue-600">다운로드</p>
              {downloadLinks.map((l, i) => (
                <LinkRow key={i} link={l} />
              ))}
            </div>
          )}
          {referenceLinks.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-purple-600">관련 게시글</p>
              {referenceLinks.map((l, i) => (
                <LinkRow key={i} link={l} isReference slug={slug} />
              ))}
            </div>
          )}
          {otherLinks.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-gray-500">기타</p>
              {otherLinks.map((l, i) => (
                <LinkRow key={i} link={l} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* 본문 */}
      <div
        className="arca-article-content border-t pt-4"
        dangerouslySetInnerHTML={{ __html: detail.content_html }}
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

function LinkRow({ link, isReference }: { link: AnalyzedLink; isReference?: boolean; slug?: string }) {
  const style = LINK_TYPE_STYLE[link.type] ?? LINK_TYPE_STYLE.other

  // arca.live 내부 링크면 앱 내 이동
  const arcaMatch = isReference && link.url.match(/arca\.live\/b\/([^/]+)\/(\d+)/)

  return (
    <div className="flex items-center gap-2 text-sm py-1">
      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${style.className}`}>
        {style.label}
      </span>
      <span className="text-muted-foreground">{link.label}</span>
      <span className="flex-1" />
      {arcaMatch ? (
        <Link
          to={`/article/${arcaMatch[1]}/${arcaMatch[2]}`}
          className="text-xs px-2 py-0.5 rounded border border-purple-300 bg-purple-50 text-purple-600 hover:bg-purple-100"
        >
          보기
        </Link>
      ) : (
        <a
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs px-2 py-0.5 rounded border border-blue-300 bg-blue-50 text-blue-600 hover:bg-blue-100"
        >
          열기 ↗
        </a>
      )}
    </div>
  )
}
