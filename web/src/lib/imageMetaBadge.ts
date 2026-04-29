const HOST_CLASS = 'nai-badge-host'
const BADGE_CLASS = 'nai-badge'
const SKIP_CLASSES = ['emoticon', 'arca-emoticon', 'twemoji']
const CONCURRENCY = 2  // arca CDN rate-limits the original-image (?type=orig) endpoint aggressively
const ROOT_MARGIN = '200px'

type LimitFn = (task: () => Promise<unknown>) => void

function createConcurrencyLimit(n: number): LimitFn {
  let active = 0
  const pending: (() => void)[] = []
  const tick = () => {
    while (active < n && pending.length > 0) {
      const fn = pending.shift()!
      active++
      fn()
    }
  }
  return (task) => {
    pending.push(() => {
      task().finally(() => {
        active--
        tick()
      })
    })
    tick()
  }
}

function shouldProcess(img: HTMLImageElement): boolean {
  if (!img.src || img.src.startsWith('data:')) return false
  for (const c of SKIP_CLASSES) {
    if (img.classList.contains(c)) return false
  }
  return true
}

function wrapWithBadgeHost(img: HTMLImageElement): void {
  if (img.parentElement?.classList.contains(HOST_CLASS)) return
  const host = document.createElement('span')
  host.className = HOST_CLASS
  const badge = document.createElement('span')
  badge.className = BADGE_CLASS
  badge.textContent = 'NAI'
  badge.style.display = 'none'
  img.replaceWith(host)
  host.appendChild(img)
  host.appendChild(badge)
}

async function fetchAndApply(
  img: HTMLImageElement,
  articleId: number,
  onOpenLightbox: ((url: string) => void) | undefined,
): Promise<void> {
  const url = img.src
  try {
    const r = await fetch(
      `/api/image-meta?article_id=${articleId}&url=${encodeURIComponent(url)}`
    )
    if (!r.ok) {
      console.warn('[image-meta] non-2xx', r.status, url)
      return
    }
    const data = (await r.json()) as { has_nai: boolean }
    if (!data.has_nai) return
    const host = img.parentElement
    if (!host) return
    const badge = host.querySelector(`.${BADGE_CLASS}`) as HTMLElement | null
    if (badge) badge.style.display = 'inline-flex'
    if (onOpenLightbox) {
      host.style.cursor = 'pointer'
      host.addEventListener('click', (e) => {
        e.preventDefault()
        e.stopPropagation()
        onOpenLightbox(url)
      })
    }
  } catch (err) {
    console.warn('[image-meta] fetch failed', err, url)
  }
}

export function attachNaiBadges(
  root: HTMLElement,
  articleId: number,
  onOpenLightbox?: (imageUrl: string) => void,
): () => void {
  const imgs = Array.from(root.querySelectorAll('img')).filter(shouldProcess)
  if (imgs.length === 0) return () => {}

  for (const img of imgs) wrapWithBadgeHost(img)

  const limit = createConcurrencyLimit(CONCURRENCY)
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        observer.unobserve(entry.target)
        const img = entry.target as HTMLImageElement
        limit(() => fetchAndApply(img, articleId, onOpenLightbox))
      }
    },
    { rootMargin: ROOT_MARGIN }
  )

  for (const img of imgs) observer.observe(img)

  return () => observer.disconnect()
}
