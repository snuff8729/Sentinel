import { useEffect, useRef, useState } from 'react'
import { Input } from '@/components/ui/input'

interface Option {
  value: string
  label: string
}

interface Props {
  value: string | null
  options: Option[]
  onChange: (value: string | null) => void
  placeholder?: string
  searchPlaceholder?: string
  allLabel?: string
  emptyLabel?: string
  triggerClassName?: string
  contentClassName?: string
}

export function ComboboxFilter({
  value,
  options,
  onChange,
  placeholder,
  searchPlaceholder = '검색...',
  allLabel = '전체',
  emptyLabel = '검색 결과 없음',
  triggerClassName = '',
  contentClassName = '',
}: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [open])

  const filtered = query
    ? options.filter(o => o.label.toLowerCase().includes(query.toLowerCase()))
    : options

  const selectedLabel = value === null
    ? (placeholder ?? allLabel)
    : options.find(o => o.value === value)?.label ?? value

  return (
    <div ref={ref} className={`relative ${triggerClassName}`}>
      <button
        type="button"
        className="flex items-center justify-between gap-1.5 rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-xs transition-colors hover:bg-muted/40 h-8 w-full outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        onClick={() => { setOpen(o => !o); setQuery('') }}
      >
        <span className={`truncate ${value === null ? 'text-muted-foreground' : ''}`}>
          {selectedLabel}
        </span>
        <span className="text-muted-foreground text-[10px]">▾</span>
      </button>
      {open && (
        <div className={`absolute z-30 mt-1 min-w-full rounded-lg border bg-popover shadow-md text-popover-foreground ${contentClassName}`}>
          <div className="p-1 border-b">
            <Input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder={searchPlaceholder}
              className="h-7 text-xs"
              autoFocus
              onKeyDown={e => {
                if (e.key === 'Enter' && filtered.length > 0) {
                  onChange(filtered[0].value)
                  setOpen(false)
                }
              }}
            />
          </div>
          <div className="max-h-60 overflow-y-auto p-1">
            <button
              type="button"
              className={`w-full text-left px-2 py-1 text-xs rounded hover:bg-muted ${value === null ? 'bg-muted/60 font-medium' : ''}`}
              onClick={() => { onChange(null); setOpen(false) }}
            >
              {allLabel}
            </button>
            {filtered.map(opt => (
              <button
                key={opt.value}
                type="button"
                className={`w-full text-left px-2 py-1 text-xs rounded hover:bg-muted truncate ${value === opt.value ? 'bg-muted/60 font-medium' : ''}`}
                onClick={() => { onChange(opt.value); setOpen(false) }}
                title={opt.label}
              >
                {opt.label}
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="px-2 py-3 text-xs text-muted-foreground text-center">{emptyLabel}</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
