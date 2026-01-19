export type ResolveMode = 'direct' | 'choose' | 'playlist'

export interface ResolveChoice {
  title: string
  url: string
}

export interface PlaylistEntry {
  index: number
  id?: string
  title: string
  duration?: number | null
  thumbnail?: string | null
  url: string
}

export interface PlaylistInfo {
  title?: string | null
  thumbnail?: string | null
  total: number
  entries: PlaylistEntry[]
}

export interface ResolveResponse {
  mode: ResolveMode
  url: string | null
  choices?: ResolveChoice[]
  playlist?: PlaylistInfo
}

export interface JobMeta {
  title?: string | null
  thumbnail_url?: string | null
  total_items?: number | null
  current_item?: number | null
  downloaded_count?: number | null
}

export interface DownloadItem {
  index: number
  title: string
  url: string
  thumbnail?: string | null
  size_bytes?: number | null
  status: 'pending' | 'downloading' | 'done' | 'error' | 'skipped' | 'paused'
  progress: number
  error_msg?: string | null
}

export interface JobResponse {
  id: string
  url: string
  status: string
  created_at: number
  updated_at: number
  progress: number
  message: string
  meta: JobMeta
  logs: string[]
  download_items?: DownloadItem[]
  download_url?: string | null
  paused?: boolean
}

export interface Track {
  id: string
  title: string
  duration_seconds?: number | null
  stream_url: string
  cover_url?: string | null
  album?: string | null
  album_title?: string | null
  created_at?: number | null
  size_bytes?: number | null
}

export interface TracksResponse {
  tracks: Track[]
}

export interface CreateJobResponse {
  job_id: string
}
