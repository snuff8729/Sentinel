import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { savedImagesApi, tagsApi } from '@/api/client'
import type { TagSummary } from '@/api/client'

export interface TagEditorProps {
  imageId: number
  tags: TagSummary[]
  onTagAdded: (tag: TagSummary) => void
  onTagRemoved: (tagId: number) => void
}

export function TagEditor({ imageId, tags, onTagAdded, onTagRemoved }: TagEditorProps) {
  const [input, setInput] = useState('')
  const [suggestions, setSuggestions] = useState<TagSummary[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!input.trim()) {
      setSuggestions([])
      return
    }
    const handle = setTimeout(async () => {
      try {
        const res = await tagsApi.search(input.trim(), 8)
        const existingValues = new Set(tags.map(t => t.value))
        setSuggestions(res.filter(s => !existingValues.has(s.value)))
      } catch {
        setSuggestions([])
      }
    }, 200)
    return () => clearTimeout(handle)
  }, [input, tags])

  const handleAdd = async (value: string) => {
    const v = value.trim().toLowerCase()
    if (!v) return
    if (tags.some(t => t.value === v)) {
      setInput('')
      setOpen(false)
      return
    }
    try {
      const res = await savedImagesApi.addTag(imageId, v)
      onTagAdded(res.tag)
      setInput('')
      setOpen(false)
    } catch {
      toast.error('태그 추가 실패')
    }
  }

  const handleRemove = async (tag: TagSummary) => {
    try {
      await savedImagesApi.removeTag(imageId, tag.id)
      onTagRemoved(tag.id)
    } catch {
      toast.error('태그 제거 실패')
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Tags ({tags.length})
      </p>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {tags.map(t => (
            <span
              key={t.id}
              className="inline-flex items-center gap-1 text-xs bg-muted px-2 py-1 rounded border"
            >
              {t.value}
              <button
                type="button"
                onClick={() => handleRemove(t)}
                className="hover:text-destructive"
                aria-label={`${t.value} 제거`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="relative">
        <input
          value={input}
          onChange={e => {
            setInput(e.target.value)
            setOpen(true)
          }}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault()
              handleAdd(input)
            } else if (e.key === 'Escape') {
              setOpen(false)
              setInput('')
            }
          }}
          onBlur={() => {
            // Allow click on dropdown item to register before closing
            setTimeout(() => setOpen(false), 150)
          }}
          placeholder="태그 입력 후 Enter (예: character:hatsune_miku)"
          className="w-full text-sm border rounded px-2 py-1"
        />
        {open && suggestions.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 border rounded bg-popover shadow-md z-10 max-h-40 overflow-y-auto">
            {suggestions.map(s => (
              <button
                key={s.id}
                type="button"
                onMouseDown={e => e.preventDefault()}
                onClick={() => handleAdd(s.value)}
                className="w-full text-left px-2 py-1 text-sm hover:bg-muted"
              >
                {s.value}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
