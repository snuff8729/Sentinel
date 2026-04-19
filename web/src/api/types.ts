export interface ChannelInfo {
  slug: string
  name: string
  icon_url: string | null
}

export interface Category {
  name: string
  slug: string
}

export interface ArticleRow {
  id: number
  title: string
  category: string | null
  comment_count: number
  author: string
  created_at: string
  view_count: number
  vote_count: number
  has_image: boolean
  has_video: boolean
  is_best: boolean
  url: string
}

export interface ArticleList {
  articles: ArticleRow[]
  current_page: number
  total_pages: number
}

export interface Attachment {
  url: string
  media_type: string
}

export interface ArticleDetail {
  id: number
  title: string
  category: string | null
  author: string
  created_at: string
  view_count: number
  vote_count: number
  down_vote_count: number
  comment_count: number
  content_html: string
  attachments: Attachment[]
}

export interface Comment {
  id: string
  author: string
  content_html: string
  created_at: string
  replies: Comment[]
}

export interface QueueStatus {
  paused: boolean
  current: { article_id: number; channel_slug: string } | null
  pending: { article_id: number; channel_slug: string }[]
}

export interface BackupHistoryItem {
  id: number
  channel_slug: string
  title: string
  author: string
  category: string | null
  url?: string
  created_at?: string
  backup_status: string
  backup_error: string | null
  backed_up_at: string | null
  analysis_status?: string
  analysis_error?: string | null
  version_group_id?: number | null
  version_label?: string | null
  download_complete?: boolean
}

export interface DownloadItem {
  id: number
  url: string
  local_path: string
  file_type: string
  status: string
  error: string | null
  warning: string | null
}

export interface ArticleLinkItem {
  id: number
  url: string
  type: string
  label: string
  source_article_id: number | null
  download_status?: string | null
  download_path?: string | null
  download_error?: string | null
}

export interface BackupDetail {
  article: BackupHistoryItem
  downloads: DownloadItem[]
  links?: ArticleLinkItem[]
  versions?: VersionRelation[]
}

export interface LLMSettings {
  base_url: string
  api_key: string
  model: string
  prompt: string
}

export interface EmbeddingSettings {
  base_url: string
  api_key: string
  model: string
}

export interface VersionRelation {
  id: number
  article_id: number
  related_article_id: number
  relation: string
  confidence: number
  llm_reason: string | null
  related_title: string
  related_id: number
}

export interface VersionGroupArticle {
  id: number
  title: string
  author: string
  version_label: string | null
  backup_status: string
  created_at: string | null
  channel_slug: string
}

export interface VersionGroupDetail {
  id: number
  name: string
  author: string | null
  article_count?: number
  articles: VersionGroupArticle[]
}

export interface UpdateCandidate {
  article_id: number
  title: string
  author: string
  matched_id: number
  matched_title: string
  similarity: number
  is_update: boolean | null
  reason: string
  group_id: number | null
  group_name: string | null
}

export interface AnalyzedLink {
  url: string
  type: 'download' | 'reference' | 'other'
  label: string
}

export interface SSEFileCompleted {
  article_id: number
  filename: string
  size_kb: number
  current: number
  total: number
  file_type: string
}

export interface SSEArticleStarted {
  article_id: number
  title: string
  total_files: number
}

export interface SSEArticleCompleted {
  article_id: number
  success_count: number
  fail_count: number
}
