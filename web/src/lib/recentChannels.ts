const STORAGE_KEY = 'sentinel_recent_channels'
const MAX_RECENT = 10

export interface RecentChannel {
  slug: string
  visitedAt: string
}

export function getRecentChannels(): RecentChannel[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    return JSON.parse(raw) as RecentChannel[]
  } catch {
    return []
  }
}

export function addRecentChannel(slug: string): void {
  const channels = getRecentChannels().filter(c => c.slug !== slug)
  channels.unshift({ slug, visitedAt: new Date().toISOString() })
  localStorage.setItem(STORAGE_KEY, JSON.stringify(channels.slice(0, MAX_RECENT)))
}
