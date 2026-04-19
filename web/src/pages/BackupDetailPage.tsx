import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { backupApi, versionApi } from '@/api/client'
import type { ArticleLinkItem, BackupDetail, DownloadItem, VersionGroupDetail } from '@/api/types'

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  completed: { label: '완료', className: 'bg-green-100 text-green-700 border-green-300' },
  failed: { label: '실패', className: 'bg-red-100 text-red-700 border-red-300' },
  in_progress: { label: '진행중', className: 'bg-blue-100 text-blue-700 border-blue-300' },
  pending: { label: '대기', className: 'bg-yellow-100 text-yellow-700 border-yellow-300' },
  cancelled: { label: '취소', className: 'bg-gray-100 text-gray-500 border-gray-300' },
}

const DL_STATUS: Record<string, { label: string; color: string }> = {
  completed: { label: '완료', color: 'text-green-600' },
  failed: { label: '실패', color: 'text-red-600' },
  pending: { label: '대기', color: 'text-yellow-600' },
  in_progress: { label: '진행중', color: 'text-blue-600' },
}

export function BackupDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [detail, setDetail] = useState<BackupDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'preview' | 'files' | 'links' | 'versions'>('preview')
  const [versionGroup, setVersionGroup] = useState<VersionGroupDetail | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    backupApi.getDetail(Number(id))
      .then(d => {
        setDetail(d)
        if (d.article?.version_group_id) {
          versionApi.getGroup(d.article.version_group_id).then(setVersionGroup).catch(() => {})
        } else {
          setVersionGroup(null)
        }
      })
      .finally(() => setLoading(false))
  }, [id])

  const handleRetry = async () => {
    if (!detail) return
    await backupApi.enqueue(detail.article.channel_slug, detail.article.id, true)
    alert('백업 큐에 다시 추가했습니다.')
  }

  if (loading) return <div className="text-center py-8 text-muted-foreground">로딩 중...</div>
  if (!detail) return <div className="text-center py-8">백업 데이터를 찾을 수 없습니다.</div>

  const { article, downloads, links = [], files = [] } = detail

  const refreshDetail = () => {
    backupApi.getDetail(Number(id)).then(d => {
      setDetail(d)
      if (d.article?.version_group_id) {
        versionApi.getGroup(d.article.version_group_id).then(setVersionGroup).catch(() => {})
      }
    })
  }
  const badgeInfo = STATUS_BADGE[article.backup_status] ?? { label: article.backup_status, className: 'bg-gray-100 text-gray-500 border-gray-300' }
  const failedCount = downloads.filter(d => d.status === 'failed').length
  const warningCount = downloads.filter(d => d.warning).length

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* 헤더 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${badgeInfo.className}`}>
            {badgeInfo.label}
          </span>
          {article.category && <Badge variant="secondary">{article.category}</Badge>}
          <h1 className="text-2xl font-bold">{article.title}</h1>
        </div>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{article.author}</span>
          <span>{article.channel_slug}</span>
          {article.created_at && (
            <span>{new Date(article.created_at).toLocaleString('ko-KR')}</span>
          )}
          {article.backed_up_at && (
            <span>백업: {new Date(article.backed_up_at).toLocaleString('ko-KR')}</span>
          )}
        </div>
        {article.backup_error && (
          <div className="text-sm text-destructive">{article.backup_error}</div>
        )}
        {article.analysis_error && (
          <div className="text-sm text-yellow-600">분석: {article.analysis_error}</div>
        )}
      </div>

      {/* 액션 */}
      <div className="flex items-center gap-2">
        {article.download_complete ? (
          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium border bg-emerald-100 text-emerald-700 border-emerald-300">
            다운로드 완료
          </span>
        ) : links.some(l => l.type === 'download') && (
          <Button size="sm" variant="outline" onClick={async () => {
            await backupApi.markDownloadComplete(article.id)
            backupApi.getDetail(article.id).then(d => {
              setDetail(d)
            })
          }}>
            다운로드 완료 처리
          </Button>
        )}
        <Button size="sm" variant="outline" onClick={handleRetry}>재시도</Button>
        <Link to={`/article/${article.channel_slug}/${article.id}`}>
          <Button size="sm" variant="outline">원본 보기 (arca.live)</Button>
        </Link>
        {article.url && (
          <a href={article.url} target="_blank" rel="noopener noreferrer">
            <Button size="sm" variant="ghost">arca.live에서 열기 ↗</Button>
          </a>
        )}
      </div>

      {/* 탭 */}
      <div className="flex gap-1 border-b">
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'preview'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('preview')}
        >
          백업 미리보기
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'files'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('files')}
        >
          파일 ({downloads.length})
          {failedCount > 0 && <span className="text-red-500 ml-1">{failedCount} 실패</span>}
          {warningCount > 0 && <span className="text-yellow-500 ml-1">{warningCount} 경고</span>}
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'links'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('links')}
        >
          자료 ({links.length + files.length})
          {article.analysis_status === 'failed' && <span className="text-red-500 ml-1">실패</span>}
          {article.analysis_status === 'pending' && <span className="text-yellow-500 ml-1">분석중</span>}
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'versions'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('versions')}
        >
          버전 ({versionGroup?.articles.length ?? 0})
        </button>
      </div>

      {/* 탭 내용 */}
      {activeTab === 'preview' && (
        <div className="border rounded-md overflow-hidden">
          <iframe
            src={`/api/backup/html/${article.id}`}
            className="w-full border-0"
            style={{ minHeight: '80vh' }}
            title="백업 미리보기"
          />
        </div>
      )}
      {activeTab === 'files' && <FileList downloads={downloads} />}
      {activeTab === 'links' && (
        <div className="space-y-6">
          <LinkList links={links} articleSlug={article.channel_slug} articleId={article.id} onUpdate={refreshDetail} />

          {/* 첨부 파일 */}
          <div className="space-y-2">
            <p className="text-sm font-medium">첨부 파일 ({files.length})</p>
            {files.length > 0 && (
              <div className="border rounded-md">
                {files.map(f => (
                  <div key={f.id} className="flex items-center gap-3 px-3 py-2 border-b last:border-b-0 text-sm hover:bg-muted/20">
                    <span className="font-mono text-xs truncate flex-1">{f.filename}</span>
                    <span className="text-xs text-muted-foreground">{(f.size / 1024).toFixed(1)}KB</span>
                    {f.note && <span className="text-xs text-muted-foreground">{f.note}</span>}
                    <button
                      className="text-xs px-2 py-0.5 rounded border border-red-300 bg-red-50 text-red-600 hover:bg-red-100"
                      onClick={async () => {
                        if (!confirm(`"${f.filename}" 파일을 삭제할까요?`)) return
                        await backupApi.deleteFreeFile(f.id)
                        refreshDetail()
                      }}
                    >
                      삭제
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div>
              <input
                type="file"
                id="free-file-upload"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0]
                  if (!file) return
                  await backupApi.uploadFreeFile(article.id, file)
                  refreshDetail()
                  e.target.value = ''
                }}
              />
              <label
                htmlFor="free-file-upload"
                className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded border border-dashed border-gray-300 text-muted-foreground hover:bg-muted cursor-pointer"
              >
                + 파일 추가
              </label>
            </div>
          </div>
        </div>
      )}
      {activeTab === 'versions' && <VersionGroupPanel group={versionGroup} currentId={article.id} />}
    </div>
  )
}

const STATUS_DOT: Record<string, string> = {
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  pending: 'bg-yellow-500',
  in_progress: 'bg-blue-500',
}

function VersionGroupPanel({ group, currentId }: { group: VersionGroupDetail | null; currentId: number }) {
  if (!group) {
    return <div className="text-center py-8 text-muted-foreground">버전 그룹이 없습니다.</div>
  }

  return (
    <div className="border rounded-md">
      <div className="px-3 py-2 bg-muted/30 border-b text-sm font-medium flex items-center gap-2">
        <span>📦</span>
        <span>{group.name}</span>
        {group.author && <span className="text-xs text-muted-foreground">by {group.author}</span>}
        <span className="text-xs text-muted-foreground">({group.articles.length}개)</span>
      </div>
      {group.articles.map(a => {
        const isCurrent = a.id === currentId
        return (
          <div
            key={a.id}
            className={`flex items-center gap-2 px-3 py-2 border-b last:border-b-0 text-sm ${isCurrent ? 'bg-blue-50' : 'hover:bg-muted/20'}`}
          >
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[a.backup_status] ?? 'bg-gray-300'}`} />
            {isCurrent ? (
              <span className="flex-1 truncate font-medium">{a.title}</span>
            ) : (
              <Link to={`/backup/${a.id}`} className="flex-1 truncate hover:underline">
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
  )
}


const LINK_TYPE_STYLE: Record<string, { label: string; className: string }> = {
  download: { label: '다운로드', className: 'bg-blue-100 text-blue-700 border-blue-300' },
  reference: { label: '관련 글', className: 'bg-purple-100 text-purple-700 border-purple-300' },
  other: { label: '기타', className: 'bg-gray-100 text-gray-500 border-gray-300' },
}

function LinkList({ links, articleSlug, articleId, onUpdate }: { links: ArticleLinkItem[]; articleSlug: string; articleId: number; onUpdate?: () => void }) {
  if (links.length === 0) {
    return <div className="text-center py-8 text-muted-foreground">분석된 링크가 없습니다.</div>
  }

  const downloadLinks = links.filter(l => l.type === 'download')
  const referenceLinks = links.filter(l => l.type === 'reference')
  const otherLinks = links.filter(l => l.type === 'other')

  return (
    <div className="space-y-4">
      {downloadLinks.length > 0 && (
        <div className="space-y-1">
          <p className="text-sm font-medium text-blue-600">다운로드 ({downloadLinks.length})</p>
          <div className="border rounded-md">
            {downloadLinks.map(l => (
              <LinkItem key={l.id} link={l} articleSlug={articleSlug} articleId={articleId} onUpdate={onUpdate} />
            ))}
          </div>
        </div>
      )}
      {referenceLinks.length > 0 && (
        <div className="space-y-1">
          <p className="text-sm font-medium text-purple-600">관련 게시글 ({referenceLinks.length})</p>
          <div className="border rounded-md">
            {referenceLinks.map(l => (
              <LinkItem key={l.id} link={l} articleSlug={articleSlug} articleId={articleId} onUpdate={onUpdate} />
            ))}
          </div>
        </div>
      )}
      {otherLinks.length > 0 && (
        <div className="space-y-1">
          <p className="text-sm font-medium text-gray-500">기타 ({otherLinks.length})</p>
          <div className="border rounded-md">
            {otherLinks.map(l => (
              <LinkItem key={l.id} link={l} articleSlug={articleSlug} articleId={articleId} onUpdate={onUpdate} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function getDomainLabel(url: string): string | null {
  try {
    const host = new URL(url).hostname
    if (host.includes('proton')) return 'Proton'
    if (host.includes('realm') || host.includes('risuai')) return 'Realm'
    if (host.includes('chub')) return 'Chub'
    if (host.includes('mega')) return 'MEGA'
    if (host.includes('catbox')) return 'Catbox'
    if (host.includes('drive.google')) return 'GDrive'
    if (host.includes('arca.live')) return null
    return host.split('.').slice(-2, -1)[0] || null
  } catch { return null }
}

const DL_STATUS_STYLE: Record<string, { label: string; className: string }> = {
  completed: { label: '받음', className: 'bg-green-100 text-green-700 border-green-300' },
  failed: { label: '실패', className: 'bg-red-100 text-red-700 border-red-300' },
  manual_required: { label: '수동', className: 'bg-amber-100 text-amber-700 border-amber-300' },
}

function LinkItem({ link }: { link: ArticleLinkItem; articleSlug?: string; articleId?: number; onUpdate?: () => void }) {
  const style = LINK_TYPE_STYLE[link.type] ?? LINK_TYPE_STYLE.other
  const arcaMatch = link.url.match(/arca\.live\/b\/([^/]+)\/(\d+)/)
  const dlStatus = link.download_status ? DL_STATUS_STYLE[link.download_status] : null
  const domainLabel = getDomainLabel(link.url)

  return (
    <div className="flex items-center gap-2 px-3 py-2 border-b last:border-b-0 text-sm hover:bg-muted/20">
      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${style.className}`}>
        {style.label}
      </span>
      {domainLabel && (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border bg-slate-100 text-slate-600 border-slate-300">
          {domainLabel}
        </span>
      )}
      {dlStatus && (
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${dlStatus.className}`} title={link.download_error || ''}>
          {dlStatus.label}
        </span>
      )}
      <span className="flex-1 truncate" title={link.download_error || ''}>{link.label}</span>
      {link.source_article_id && (
        <span className="text-xs text-muted-foreground">← #{link.source_article_id}</span>
      )}
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

function FileList({ downloads }: { downloads: DownloadItem[] }) {
  return (
    <div className="border rounded-md">
      {downloads.map(d => {
        const dlStatus = DL_STATUS[d.status] ?? { label: d.status, color: '' }
        return (
          <div key={d.id} className="flex items-center gap-3 px-3 py-2 border-b last:border-b-0 text-sm hover:bg-muted/20">
            <span className="font-mono text-xs truncate flex-1" title={d.url}>
              {d.local_path.split('/').pop()}
            </span>
            <span className="w-16 text-xs text-muted-foreground">{d.file_type}</span>
            <span className={`w-12 text-xs font-medium ${dlStatus.color}`}>{dlStatus.label}</span>
            <span className="flex-1 text-xs truncate">
              {d.error && <span className="text-red-600">{d.error}</span>}
              {d.warning && <span className="text-yellow-600">⚠ {d.warning}</span>}
            </span>
          </div>
        )
      })}
    </div>
  )
}
