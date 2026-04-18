import type {
  ArticleDetail,
  ArticleList,
  BackupDetail,
  BackupHistoryItem,
  Category,
  ChannelInfo,
  Comment,
  QueueStatus,
} from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const channelApi = {
  getInfo: (slug: string) =>
    get<ChannelInfo>(`/channel/${slug}/info`),

  getCategories: (slug: string) =>
    get<Category[]>(`/channel/${slug}/categories`),

  getArticles: (slug: string, params?: {
    category?: string
    mode?: string
    sort?: string
    cut?: number
    page?: number
  }) => {
    const searchParams = new URLSearchParams()
    if (params?.category) searchParams.set('category', params.category)
    if (params?.mode) searchParams.set('mode', params.mode)
    if (params?.sort) searchParams.set('sort', params.sort)
    if (params?.cut) searchParams.set('cut', String(params.cut))
    if (params?.page) searchParams.set('page', String(params.page))
    const qs = searchParams.toString()
    return get<ArticleList>(`/channel/${slug}/articles${qs ? `?${qs}` : ''}`)
  },

  search: (slug: string, keyword: string, target = 'all', page = 1) =>
    get<ArticleList>(`/channel/${slug}/search?keyword=${encodeURIComponent(keyword)}&target=${target}&page=${page}`),
}

export const articleApi = {
  getDetail: (slug: string, id: number) =>
    get<ArticleDetail>(`/article/${slug}/${id}`),

  getComments: (slug: string, id: number) =>
    get<Comment[]>(`/article/${slug}/${id}/comments`),
}

export const backupApi = {
  enqueue: (slug: string, articleId: number, force = false) =>
    post<{ status: string; position: number }>(`/backup/${slug}/${articleId}${force ? '?force=true' : ''}`),

  cancel: (articleId: number) =>
    del<{ status: string }>(`/backup/${articleId}`),

  pause: () => post<{ status: string }>('/backup/pause'),
  resume: () => post<{ status: string }>('/backup/resume'),

  getQueue: () => get<QueueStatus>('/backup/queue'),

  getDetail: (articleId: number) =>
    get<BackupDetail>(`/backup/detail/${articleId}`),

  getHistory: (status?: string) =>
    get<BackupHistoryItem[]>(`/backup/history${status ? `?status=${status}` : ''}`),

  getStatuses: async (ids: number[]) => {
    const res = await fetch(`${BASE}/backup/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ids),
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json() as Promise<Record<string, string>>
  },
}
