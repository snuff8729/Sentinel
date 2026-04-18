export interface Category {
  name: string
  slug: string
}

export interface ArticleRow {
  id: number
  num: number
  title: string
  category: string | null
  comment_count: number
  author: string
  created_at: string
  view_count: number
  vote_count: number
  has_image: boolean
  has_video: boolean
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
  backup_status: string
  backup_error: string | null
  backed_up_at: string | null
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
