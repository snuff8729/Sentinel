import { useEffect, useState } from 'react'
import { Dialog, DialogContent } from '@/components/ui/dialog'

export interface NaiMetadata {
  prompt?: string
  negative?: string
  steps?: number
  cfg_scale?: number
  cfg_rescale?: number
  seed?: number
  sampler?: string
  scheduler?: string
  width?: number
  height?: number
  characters?: { prompt: string; negative: string }[]
  source?: string
}

export interface NaiMetadataDialogProps {
  open: boolean
  onOpenChange: (v: boolean) => void
  imageUrl: string | null
  articleId: number | null
}

export function NaiMetadataDialog({ open, onOpenChange, imageUrl, articleId }: NaiMetadataDialogProps) {
  const [meta, setMeta] = useState<NaiMetadata | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!open || !imageUrl || articleId == null) return
    let cancelled = false
    setLoading(true)
    setError(false)
    setMeta(null)
    fetch(`/api/image-meta?article_id=${articleId}&url=${encodeURIComponent(imageUrl)}&include=full`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (cancelled) return
        setMeta((data.metadata as NaiMetadata | undefined) ?? null)
      })
      .catch((err) => {
        console.warn('[image-meta] full fetch failed', err)
        if (!cancelled) setError(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, imageUrl, articleId])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-7xl w-[95vw] h-[90vh] p-0 gap-0 overflow-hidden">
        <div className="flex flex-col md:flex-row h-full">
          <div className="flex-1 bg-black/90 flex items-center justify-center overflow-hidden">
            {imageUrl && (
              <a href={imageUrl} target="_blank" rel="noreferrer" className="block max-h-full max-w-full">
                <img
                  src={imageUrl}
                  className="max-h-[90vh] max-w-full object-contain"
                  referrerPolicy="no-referrer"
                  alt=""
                />
              </a>
            )}
          </div>
          <div className="w-full md:w-[400px] border-l overflow-y-auto p-4 space-y-4">
            {loading && <p className="text-sm text-muted-foreground">메타데이터 로딩 중...</p>}
            {error && <p className="text-sm text-destructive">메타데이터를 불러올 수 없습니다.</p>}
            {!loading && !error && !meta && <p className="text-sm text-muted-foreground">메타데이터 없음</p>}
            {meta && <MetadataPanel meta={meta} />}
          </div>
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
      console.warn('[image-meta] clipboard write failed')
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
