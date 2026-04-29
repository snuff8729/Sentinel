import { toast } from 'sonner'

const HOST_CLASS = 'save-btn-host'
const BUTTON_CLASS = 'save-btn'
const SKIP_CLASSES = ['emoticon', 'arca-emoticon', 'twemoji']

const ICON_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'

function shouldProcess(img: HTMLImageElement): boolean {
  if (!img.src || img.src.startsWith('data:')) return false
  for (const c of SKIP_CLASSES) {
    if (img.classList.contains(c)) return false
  }
  return true
}

function wrapWithButtonHost(img: HTMLImageElement, articleId: number): void {
  if (img.parentElement?.classList.contains(HOST_CLASS)) return
  const host = document.createElement('span')
  host.className = HOST_CLASS
  const btn = document.createElement('button')
  btn.className = BUTTON_CLASS
  btn.type = 'button'
  btn.title = '저장'
  btn.innerHTML = ICON_SVG
  btn.addEventListener('click', (e) => {
    e.preventDefault()
    e.stopPropagation()
    handleSaveClick(img.src, articleId)
  })
  img.replaceWith(host)
  host.appendChild(img)
  host.appendChild(btn)
}

async function handleSaveClick(url: string, articleId: number): Promise<void> {
  try {
    const r = await fetch('/api/saved-images', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ article_id: articleId, url }),
    })
    if (!r.ok) {
      toast.error(`저장 실패: HTTP ${r.status}`)
      return
    }
    const data = (await r.json()) as { status: string; error?: string }
    if (data.status === 'queued') {
      toast.success('저장 큐에 추가됨')
    } else if (data.status === 'already_saved') {
      toast.info('이미 저장된 이미지입니다')
    } else if (data.status === 'error') {
      toast.error(`저장 실패: ${data.error ?? 'unknown'}`)
    }
  } catch (err) {
    console.warn('[save] request failed', err)
    toast.error('저장 요청 실패')
  }
}

export function attachSaveButtons(root: HTMLElement, articleId: number): () => void {
  const imgs = Array.from(root.querySelectorAll('img')).filter(shouldProcess)
  for (const img of imgs) wrapWithButtonHost(img, articleId)
  return () => {}
}
