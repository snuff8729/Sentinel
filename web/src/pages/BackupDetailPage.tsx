import { useEffect, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { backupApi, versionApi } from '@/api/client'
import type { ArticleFileItem, ArticleLinkItem, BackupDetail, DownloadItem, VersionGroupDetail } from '@/api/types'

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
            activeTab === 'links'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('links')}
        >
          자료 ({files.length})
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
        <ResourcesTab
          links={links}
          files={files}
          articleId={article.id}
          articleSlug={article.channel_slug}
          onUpdate={refreshDetail}
        />
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

function ResourcesTab({ links, files, articleId, articleSlug, onUpdate }: {
  links: ArticleLinkItem[]
  files: ArticleFileItem[]
  articleId: number
  articleSlug: string
  onUpdate: () => void
}) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)

  const uploadFiles = useCallback(async (fileList: FileList | File[]) => {
    setUploading(true)
    try {
      for (const file of Array.from(fileList)) {
        await backupApi.uploadFreeFile(articleId, file)
      }
      onUpdate()
    } catch (e) {
      alert(`업로드 실패: ${e}`)
    } finally {
      setUploading(false)
    }
  }, [articleId, onUpdate])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length > 0) {
      uploadFiles(e.dataTransfer.files)
    }
  }, [uploadFiles])

  return (
    <div
      className={`space-y-6 relative rounded-md transition-colors ${dragging ? 'bg-blue-50 ring-2 ring-blue-300 ring-dashed' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {dragging && (
        <div className="absolute inset-0 flex items-center justify-center bg-blue-50/80 rounded-md z-10 pointer-events-none">
          <p className="text-blue-600 font-medium">파일을 놓으면 업로드됩니다</p>
        </div>
      )}

      {uploading && (
        <div className="text-sm p-2 rounded border bg-blue-50 border-blue-200 text-blue-600">
          업로드 중...
        </div>
      )}

      <LinkList links={links} articleSlug={articleSlug} articleId={articleId} onUpdate={onUpdate} />

      {/* 첨부 파일 */}
      <div className="space-y-2">
        <p className="text-sm font-medium">첨부 파일 ({files.length})</p>
        {files.length > 0 && (
          <div className="border rounded-md">
            {files.map(f => (
              <FileItem key={f.id} file={f} downloadLinks={links.filter(l => l.type === 'download')} onUpdate={onUpdate} />
            ))}
          </div>
        )}
        <div>
          <input
            type="file"
            id="free-file-upload"
            className="hidden"
            multiple
            onChange={async (e) => {
              if (e.target.files && e.target.files.length > 0) {
                await uploadFiles(e.target.files)
              }
              e.target.value = ''
            }}
          />
          <label
            htmlFor="free-file-upload"
            className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded border border-dashed border-gray-300 text-muted-foreground hover:bg-muted cursor-pointer"
          >
            + 파일 추가 (또는 여기에 드래그)
          </label>
        </div>
      </div>
    </div>
  )
}

function FileItem({ file, downloadLinks = [], onUpdate }: { file: ArticleFileItem; downloadLinks?: ArticleLinkItem[]; onUpdate: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const [editAlias, setEditAlias] = useState(file.filename)
  const [editNote, setEditNote] = useState(file.note || '')
  const [editLinkId, setEditLinkId] = useState<number | null>(file.source_link_id)
  const [saving, setSaving] = useState(false)

  const linkedLink = downloadLinks.find(l => l.id === file.source_link_id)

  const handleSave = async () => {
    setSaving(true)
    try {
      await backupApi.updateFreeFile(file.id, { filename: editAlias, note: editNote, source_link_id: editLinkId })
      onUpdate()
    } finally {
      setSaving(false)
    }
  }

  const sizeLabel = file.size >= 1024 * 1024
    ? `${(file.size / 1024 / 1024).toFixed(1)}MB`
    : `${(file.size / 1024).toFixed(1)}KB`

  return (
    <div className="border-b last:border-b-0">
      <div
        className="flex items-center gap-3 px-3 py-2 text-sm hover:bg-muted/20 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-muted-foreground text-xs">{expanded ? '▼' : '▶'}</span>
        <span className="font-mono text-xs truncate flex-1">{file.filename}</span>
        <span className="text-xs text-muted-foreground">{sizeLabel}</span>
        {linkedLink && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border bg-blue-50 text-blue-600 border-blue-200 truncate max-w-[120px]" title={linkedLink.label}>
            🔗 {getDomainLabel(linkedLink.url) || '링크'}
          </span>
        )}
        {file.note && !linkedLink && <span className="text-xs text-muted-foreground truncate max-w-[150px]">{file.note}</span>}
        <button
          className="text-xs px-2 py-0.5 rounded border border-red-300 bg-red-50 text-red-600 hover:bg-red-100"
          onClick={async (e) => {
            e.stopPropagation()
            if (!confirm(`"${file.filename}" 파일을 삭제할까요?`)) return
            await backupApi.deleteFreeFile(file.id)
            onUpdate()
          }}
        >
          삭제
        </button>
      </div>
      {expanded && (
        <div className="px-3 pb-3 pt-1 bg-muted/10 space-y-2">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">파일명 (별칭)</label>
            <input
              className="w-full text-sm border rounded px-2 py-1"
              value={editAlias}
              onChange={e => setEditAlias(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">연결된 다운로드 링크</label>
            <Select
              value={editLinkId != null ? String(editLinkId) : '_none'}
              onValueChange={(v) => v && setEditLinkId(v === '_none' ? null : Number(v))}
            >
              <SelectTrigger className="w-full text-sm">
                <SelectValue placeholder="없음" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_none">없음</SelectItem>
                {downloadLinks.map(l => (
                  <SelectItem key={l.id} value={String(l.id)}>
                    [{getDomainLabel(l.url) || '링크'}] {l.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {downloadLinks.length === 0 && (
              <p className="text-xs text-muted-foreground">다운로드 링크가 분석되지 않았습니다.</p>
            )}
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">노트</label>
            <textarea
              className="w-full text-sm border rounded px-2 py-1 min-h-[60px]"
              value={editNote}
              onChange={e => setEditNote(e.target.value)}
              placeholder="메모를 입력하세요..."
            />
          </div>
          <div className="flex gap-2">
            <button
              className="text-xs px-3 py-1 rounded border border-blue-300 bg-blue-50 text-blue-600 hover:bg-blue-100"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? '저장 중...' : '저장'}
            </button>
            <button
              className="text-xs px-3 py-1 rounded border text-muted-foreground hover:bg-muted"
              onClick={() => { setExpanded(false); setEditAlias(file.filename); setEditNote(file.note || '') }}
            >
              취소
            </button>
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

function LinkItem({ link }: { link: ArticleLinkItem; articleSlug?: string; articleId?: number; onUpdate?: () => void }) {
  const style = LINK_TYPE_STYLE[link.type] ?? LINK_TYPE_STYLE.other
  const arcaMatch = link.url.match(/arca\.live\/b\/([^/]+)\/(\d+)/)
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
      <span className="flex-1 truncate">{link.label}</span>
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
