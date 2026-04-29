import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { savedImagesApi } from '@/api/client'
import type { NaiMetadata, SavedImageItem, TagSummary } from '@/api/client'
import { TagEditor } from '@/components/TagEditor'

export interface SavedImageDialogProps {
  open: boolean
  imageId: number | null
  onClose: () => void
  onDeleted: (id: number) => void
  onTagsChanged: (id: number, tags: TagSummary[]) => void
}

export function SavedImageDialog({
  open,
  imageId,
  onClose,
  onDeleted,
  onTagsChanged,
}: SavedImageDialogProps) {
  const [data, setData] = useState<SavedImageItem | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!open || imageId == null) return
    let cancelled = false
    setLoading(true)
    setError(false)
    setData(null)
    savedImagesApi
      .get(imageId)
      .then(d => {
        if (!cancelled) setData(d)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, imageId])

  const handleTagAdded = (tag: TagSummary) => {
    if (!data) return
    const newTags = [...data.tags, tag]
    setData({ ...data, tags: newTags })
    onTagsChanged(data.id, newTags)
  }

  const handleTagRemoved = (tagId: number) => {
    if (!data) return
    const newTags = data.tags.filter(t => t.id !== tagId)
    setData({ ...data, tags: newTags })
    onTagsChanged(data.id, newTags)
  }

  const handleDelete = async () => {
    if (!data) return
    try {
      await savedImagesApi.delete(data.id)
      onDeleted(data.id)
      onClose()
      toast.success('삭제됨')
    } catch {
      toast.error('삭제 실패')
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent
        showCloseButton={false}
        className="!grid-cols-1 max-w-7xl w-[95vw] h-[90vh] p-0 gap-0 overflow-hidden flex flex-col md:flex-row"
      >
        <div className="flex-1 min-h-0 bg-black/90 flex items-center justify-center overflow-hidden relative">
          {data?.file_path && (
            <img
              src={`/data/${data.file_path}`}
              className="max-h-full max-w-full object-contain"
              alt=""
            />
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="absolute top-2 right-2 w-8 h-8 inline-flex items-center justify-center rounded bg-black/60 text-white hover:bg-black/80"
          >
            ×
          </button>
        </div>
        <div className="w-full md:w-[400px] md:h-full md:max-h-full max-h-[40vh] border-l overflow-y-auto p-4 space-y-4">
          {loading && <p className="text-sm text-muted-foreground">로딩...</p>}
          {error && <p className="text-sm text-destructive">로드 실패</p>}
          {data?.payload_json && <MetadataPanel meta={data.payload_json} />}
          {data && (
            <TagEditor
              imageId={data.id}
              tags={data.tags}
              onTagAdded={handleTagAdded}
              onTagRemoved={handleTagRemoved}
            />
          )}
          {data && (
            <div className="flex justify-between items-center pt-4 border-t text-xs text-muted-foreground gap-2">
              {data.channel_slug ? (
                <a
                  href={`/article/${data.channel_slug}/${data.article_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:underline"
                >
                  글 #{data.article_id} · 원본 열기 ↗
                </a>
              ) : (
                <span className="opacity-60">글 #{data.article_id}</span>
              )}
              <ConfirmDialog
                trigger={
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive border-destructive/40 hover:bg-destructive/10"
                  >
                    삭제
                  </Button>
                }
                title="이미지 삭제"
                description="이 저장된 이미지와 EXIF 사이드카, 태그 연결을 모두 삭제합니다."
                confirmText="삭제"
                onConfirm={handleDelete}
              />
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

function MetadataPanel({ meta }: { meta: NaiMetadata }) {
  return (
    <div className="space-y-4">
      {meta.prompt && <PromptBlock label="Prompt" text={meta.prompt} maxHeightClass="max-h-48" />}
      {meta.negative && <PromptBlock label="Negative" text={meta.negative} maxHeightClass="max-h-32" />}

      {meta.characters && meta.characters.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Characters ({meta.characters.length})
          </p>
          {meta.characters.map((c, i) => (
            <CharacterCard key={i} idx={i} char={c} />
          ))}
        </div>
      )}

      <div className="border-t pt-2 space-y-1">
        {meta.width != null && meta.height != null && (
          <ParamRow label="Size" value={`${meta.width} × ${meta.height}`} />
        )}
        {meta.steps != null && <ParamRow label="Steps" value={meta.steps} />}
        {meta.cfg_scale != null && <ParamRow label="CFG" value={meta.cfg_scale} />}
        {meta.cfg_rescale != null && <ParamRow label="CFG Rescale" value={meta.cfg_rescale} />}
        {meta.seed != null && <ParamRow label="Seed" value={meta.seed} />}
        {meta.sampler && <ParamRow label="Sampler" value={meta.sampler} />}
        {meta.scheduler && <ParamRow label="Scheduler" value={meta.scheduler} />}
      </div>
    </div>
  )
}

function PromptBlock({
  label,
  text,
  maxHeightClass,
}: {
  label: string
  text: string
  maxHeightClass: string
}) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      console.warn('[saved] clipboard write failed')
    }
  }
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <button
          type="button"
          onClick={handleCopy}
          className="text-xs px-2 py-0.5 rounded border hover:bg-muted"
        >
          {copied ? '복사됨' : '복사'}
        </button>
      </div>
      <pre
        className={`text-xs whitespace-pre-wrap break-words bg-muted/30 rounded p-2 ${maxHeightClass} overflow-y-auto font-sans`}
      >
        {text}
      </pre>
    </div>
  )
}

function ParamRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between text-sm py-0.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  )
}

function CharacterCard({ idx, char }: { idx: number; char: { prompt: string; negative: string } }) {
  return (
    <div className="border rounded p-2 space-y-1">
      <p className="text-xs font-medium">캐릭터 #{idx + 1}</p>
      {char.prompt && <PromptBlock label="Pos" text={char.prompt} maxHeightClass="max-h-24" />}
      {char.negative && <PromptBlock label="Neg" text={char.negative} maxHeightClass="max-h-24" />}
    </div>
  )
}
