import type {
  ArticleDetail,
  ArticleList,
  BackupDetail,
  BackupHistoryItem,
  Category,
  ChannelInfo,
  EmbeddingSettings,
  QueueStatus,
  UpdateCandidate,
  VersionGroupDetail,
} from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method: 'POST' }
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
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

  checkUpdates: (slug: string, articles: { id: number; title: string; author: string }[]) =>
    post<{ updates: UpdateCandidate[] }>(`/channel/${slug}/check-updates`, articles),

  search: (slug: string, keyword: string, target = 'all', page = 1, params?: {
    category?: string
    mode?: string
  }) => {
    const searchParams = new URLSearchParams()
    searchParams.set('keyword', keyword)
    searchParams.set('target', target)
    searchParams.set('page', String(page))
    if (params?.category) searchParams.set('category', params.category)
    if (params?.mode) searchParams.set('mode', params.mode)
    return get<ArticleList>(`/channel/${slug}/search?${searchParams.toString()}`)
  },
}

export const articleApi = {
  getDetail: (slug: string, id: number) =>
    get<ArticleDetail>(`/article/${slug}/${id}`),

  getComments: (slug: string, id: number) =>
    get<{ html: string }>(`/article/${slug}/${id}/comments`),

}

export const versionApi = {
  listGroups: () => get<VersionGroupDetail[]>('/versions/'),
  createGroup: (name: string, author?: string) =>
    post<{ id: number; name: string }>('/versions/', { name, author }),
  getGroup: (groupId: number) => get<VersionGroupDetail>(`/versions/${groupId}`),
  renameGroup: (groupId: number, name: string) =>
    put<{ status: string }>(`/versions/${groupId}`, { name }),
  deleteGroup: (groupId: number) =>
    del<{ status: string }>(`/versions/${groupId}`),
  addArticle: (groupId: number, articleId: number, versionLabel?: string) =>
    post<{ status: string }>(`/versions/${groupId}/articles`, { article_id: articleId, version_label: versionLabel }),
  removeArticle: (groupId: number, articleId: number) =>
    del<{ status: string }>(`/versions/${groupId}/articles/${articleId}`),
  searchGroups: (keyword: string) =>
    get<{ id: number; name: string; author: string | null; article_count: number }[]>(`/versions/search/${encodeURIComponent(keyword)}`),
}

export const followApi = {
  list: () => get<{ username: string; note: string | null }[]>('/follow/'),
  usernames: () => get<string[]>('/follow/usernames'),
  follow: (username: string, note?: string) =>
    post<{ status: string }>('/follow/', { username, note }),
  unfollow: (username: string) =>
    del<{ status: string }>(`/follow/${encodeURIComponent(username)}`),
}

export const settingsApi = {
  getDataPath: () => get<{ path: string; exists: boolean; total_size_mb: number; file_count: number }>('/settings/data-path'),
  updateDataPath: (path: string) => put<{ status: string; path?: string; error?: string }>('/settings/data-path', { path }),

  getEmbedding: () => get<EmbeddingSettings>('/settings/embedding'),
  updateEmbedding: (settings: EmbeddingSettings) => put<{ status: string; model_changed?: boolean }>('/settings/embedding', settings),
  testEmbedding: (settings: EmbeddingSettings) => post<{ success: boolean; dimensions?: number; error?: string }>('/settings/embedding/test', settings),
  getEmbeddingStatus: () => get<{ stale: boolean; embedded_count: number; total_articles: number }>('/settings/embedding/status'),
  recalculateEmbeddings: () => post<{ success: number; failed: number; total: number }>('/settings/embedding/recalculate'),
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

  uploadFreeFile: async (articleId: number, file: File, note?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    if (note) formData.append('note', note)
    const res = await fetch(`${BASE}/backup/upload-free/${articleId}`, {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json() as Promise<{ status: string; filename: string; size_kb: number }>
  },

  updateFreeFile: (fileId: number, data: { filename?: string; note?: string; source_link_id?: number | null }) =>
    put<{ status: string }>(`/backup/file/${fileId}`, data),

  deleteFreeFile: (fileId: number) =>
    del<{ status: string }>(`/backup/file/${fileId}`),

  markDownloadComplete: (articleId: number) =>
    post<{ status: string }>(`/backup/complete-download/${articleId}`),

  getStatuses: async (ids: number[]) => {
    const res = await fetch(`${BASE}/backup/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ids),
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json() as Promise<Record<string, { status: string; group_name: string | null; group_id: number | null }>>
  },
}
