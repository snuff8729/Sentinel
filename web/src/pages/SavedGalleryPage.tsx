import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { savedImagesApi } from '@/api/client'
import type { SavedImageItem, TagSummary } from '@/api/client'
import { SavedImageDialog } from '@/components/SavedImageDialog'

const PAGE_SIZE = 60

type FilterMode = 'all' | 'untagged' | 'no_exif'

export function SavedGalleryPage() {
  const [items, setItems] = useState<SavedImageItem[]>([])
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<FilterMode>('all')
  const [tagPrefixInput, setTagPrefixInput] = useState('')
  const [debouncedPrefix, setDebouncedPrefix] = useState('')
  const [openId, setOpenId] = useState<number | null>(null)
  const reloadRef = useRef(0)

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedPrefix(tagPrefixInput), 200)
    return () => clearTimeout(handle)
  }, [tagPrefixInput])

  const buildParams = (offset: number) => ({
    offset,
    limit: PAGE_SIZE,
    untagged: mode === 'untagged',
    no_exif: mode === 'no_exif',
    tag_prefix: mode === 'all' ? debouncedPrefix || undefined : undefined,
  })

  useEffect(() => {
    reloadRef.current++
    const myReload = reloadRef.current
    setItems([])
    setHasMore(true)
    setLoading(true)
    savedImagesApi
      .list(buildParams(0))
      .then(data => {
        if (reloadRef.current !== myReload) return
        setItems(data.items)
        setHasMore(data.has_more)
      })
      .catch(() => {
        if (reloadRef.current !== myReload) return
        setItems([])
        setHasMore(false)
      })
      .finally(() => {
        if (reloadRef.current !== myReload) return
        setLoading(false)
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, debouncedPrefix])

  const loadMore = () => {
    if (loading || !hasMore) return
    const myReload = reloadRef.current
    setLoading(true)
    savedImagesApi
      .list(buildParams(items.length))
      .then(data => {
        if (reloadRef.current !== myReload) return
        setItems(prev => [...prev, ...data.items])
        setHasMore(data.has_more)
      })
      .finally(() => {
        if (reloadRef.current !== myReload) return
        setLoading(false)
      })
  }

  const handleDeleted = (deletedId: number) => {
    setItems(prev => prev.filter(i => i.id !== deletedId))
  }

  const handleTagsChanged = (id: number, tags: TagSummary[]) => {
    setItems(prev => prev.map(i => (i.id === id ? { ...i, tags } : i)))
  }

  const handleModeChange = (next: FilterMode) => {
    setMode(next)
    if (next !== 'all') setTagPrefixInput('')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Button
          variant={mode === 'all' ? 'default' : 'outline'}
          size="sm"
          onClick={() => handleModeChange('all')}
        >
          전체
        </Button>
        <Button
          variant={mode === 'untagged' ? 'default' : 'outline'}
          size="sm"
          onClick={() => handleModeChange('untagged')}
        >
          태그 없음
        </Button>
        <Button
          variant={mode === 'no_exif' ? 'default' : 'outline'}
          size="sm"
          onClick={() => handleModeChange('no_exif')}
        >
          EXIF 없음
        </Button>
        <Input
          value={tagPrefixInput}
          disabled={mode !== 'all'}
          onChange={e => setTagPrefixInput(e.target.value)}
          placeholder="태그 검색 (예: character:)"
          className="max-w-sm ml-auto"
        />
      </div>

      {items.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
          {items.map(item => (
            <button
              key={item.id}
              type="button"
              onClick={() => setOpenId(item.id)}
              className="relative block aspect-square overflow-hidden rounded border hover:ring-2 hover:ring-primary"
            >
              {item.file_path && (
                <img
                  src={`/data/${item.file_path}`}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  alt=""
                />
              )}
              {item.payload_json == null && (
                <span className="absolute top-1 right-1 px-1.5 py-0.5 rounded bg-black/70 text-white text-[10px] font-medium tracking-wide pointer-events-none">
                  EXIF 없음
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {loading && <div className="text-center py-4 text-muted-foreground">로딩 중...</div>}
      {hasMore && !loading && items.length > 0 && (
        <div className="text-center">
          <Button onClick={loadMore} variant="outline">더 보기</Button>
        </div>
      )}
      {items.length === 0 && !loading && (
        <div className="text-center py-12 text-muted-foreground">저장된 이미지가 없습니다.</div>
      )}

      <SavedImageDialog
        open={openId !== null}
        imageId={openId}
        onClose={() => setOpenId(null)}
        onDeleted={handleDeleted}
        onTagsChanged={handleTagsChanged}
      />
    </div>
  )
}
