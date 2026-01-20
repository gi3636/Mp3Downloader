import type { CreateJobResponse, JobResponse, ResolveResponse, TracksResponse } from './types'

interface FetchOptions extends RequestInit {
  timeout?: number
  retries?: number
  retryDelay?: number
}

const DEFAULT_TIMEOUT = 30000 // 30秒
const DEFAULT_RETRIES = 2
const DEFAULT_RETRY_DELAY = 1000

async function fetchWithTimeout(input: RequestInfo | URL, init?: FetchOptions): Promise<Response> {
  const timeout = init?.timeout ?? DEFAULT_TIMEOUT
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)
  
  try {
    const response = await fetch(input, {
      ...init,
      signal: controller.signal,
    })
    return response
  } finally {
    clearTimeout(timeoutId)
  }
}

async function fetchJson<T>(input: RequestInfo | URL, init?: FetchOptions): Promise<T> {
  const retries = init?.retries ?? DEFAULT_RETRIES
  const retryDelay = init?.retryDelay ?? DEFAULT_RETRY_DELAY
  
  let lastError: Error | null = null
  
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetchWithTimeout(input, init)
      
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const msg = (data as any)?.error || (data as any)?.message || 'Request failed'
        const err = new Error(msg) as any
        err.status = res.status
        err.data = data
        throw err
      }
      return data as T
    } catch (e: any) {
      lastError = e
      
      // 不重试的情况：非网络错误、超时、或服务器明确返回错误
      if (e.name === 'AbortError') {
        throw new Error('请求超时，请检查网络连接或稍后重试')
      }
      if (e.status && e.status < 500) {
        throw e // 4xx 错误不重试
      }
      
      // 网络错误或 5xx 错误，尝试重试
      if (attempt < retries) {
        console.log(`请求失败，${retryDelay}ms 后重试 (${attempt + 1}/${retries})...`)
        await new Promise(resolve => setTimeout(resolve, retryDelay))
        continue
      }
      
      // 所有重试都失败
      if (e.message === 'Failed to fetch' || e.name === 'TypeError') {
        throw new Error('网络连接失败，请检查后端服务是否运行')
      }
      throw e
    }
  }
  
  throw lastError || new Error('请求失败')
}

export function resolveUrl(url: string) {
  return fetchJson<ResolveResponse>('/api/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
    timeout: 120000, // 解析可能需要较长时间，设置2分钟超时
    retries: 1, // 解析只重试1次
  })
}

export function createJob(body: { url: string; video_urls?: string[]; video_titles?: string[]; video_thumbnails?: string[]; force_single?: boolean }) {
  return fetchJson<CreateJobResponse>('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    timeout: 60000, // 创建任务可能需要一些时间
  })
}

export function getJob(jobId: string) {
  return fetchJson<JobResponse>(`/api/jobs/${jobId}`)
}

export interface JobListItem {
  id: string
  url: string
  status: string
  created_at: number
  updated_at: number
  progress: number
  message: string
  meta: {
    title: string | null
    thumbnail_url: string | null
    total_items: number | null
  }
  paused: boolean
}

export function listJobs() {
  return fetchJson<{ jobs: JobListItem[] }>('/api/jobs')
}

export function cancelJob(jobId: string) {
  return fetchJson<{ ok: boolean }>(`/api/jobs/${jobId}/cancel`, { method: 'POST' })
}

export function pauseJob(jobId: string) {
  return fetchJson<{ ok: boolean }>(`/api/jobs/${jobId}/pause`, { method: 'POST' })
}

export function resumeJob(jobId: string) {
  return fetchJson<{ ok: boolean }>(`/api/jobs/${jobId}/resume`, { method: 'POST' })
}

export function pauseJobItem(jobId: string, itemIndex: number) {
  return fetchJson<{ ok: boolean }>(`/api/jobs/${jobId}/items/${itemIndex}/pause`, { method: 'POST' })
}

export function resumeJobItem(jobId: string, itemIndex: number) {
  return fetchJson<{ ok: boolean }>(`/api/jobs/${jobId}/items/${itemIndex}/resume`, { method: 'POST' })
}

export function deleteJob(jobId: string) {
  return fetchJson<{ ok: boolean }>(`/api/jobs/${jobId}/delete`, { method: 'POST' })
}

export async function getJobTracks(jobId: string): Promise<TracksResponse> {
  return fetchJson<TracksResponse>(`/api/jobs/${jobId}/tracks`)
}

export function deleteJobTrack(jobId: string, trackId: string) {
  return fetchJson<{ ok: boolean }>(`/api/jobs/${jobId}/tracks/${trackId}/delete`, { method: 'POST' })
}

export function getLibraryTracks() {
  return fetchJson<TracksResponse>('/api/library/tracks')
}

export function deleteLibraryTrack(trackId: string) {
  return fetchJson<{ ok: boolean }>(`/api/library/tracks/${trackId}/delete`, { method: 'POST' })
}

// 设置相关 API
export interface Settings {
  download_dir: string
}

export function getSettings() {
  return fetchJson<Settings>('/api/settings')
}

export function saveSettings(settings: Partial<Settings>) {
  return fetchJson<{ ok: boolean }>('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
}

export interface MigrationCheck {
  need_migration: boolean
  file_count: number
  total_size: number
  old_dir: string
  new_dir: string
}

export function checkMigration(newDir: string) {
  return fetchJson<MigrationCheck>('/api/settings/check-migration', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_dir: newDir }),
  })
}

export function migrateFiles(newDir: string, deleteSource: boolean = true) {
  return fetchJson<{ ok: boolean; migrated_count: number }>('/api/settings/migrate-files', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_dir: newDir, delete_source: deleteSource }),
  })
}

export function openDownloadFolder() {
  return fetchJson<{ ok: boolean }>('/api/settings/open-folder', { method: 'POST' })
}

export function openJobFolder(jobId: string) {
  return fetchJson<{ ok: boolean }>(`/api/jobs/${jobId}/open-folder`, { method: 'POST' })
}

// 播放列表管理 API
export interface Playlist {
  id: string
  name: string
  folder: string
  track_count: number
}

export function getPlaylists() {
  return fetchJson<{ playlists: Playlist[] }>('/api/playlists')
}

export function createPlaylist(name: string) {
  return fetchJson<Playlist>('/api/playlists', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function renamePlaylist(playlistId: string, name: string) {
  return fetchJson<Playlist>(`/api/playlists/${playlistId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function deletePlaylist(playlistId: string) {
  return fetchJson<{ ok: boolean }>(`/api/playlists/${playlistId}`, { method: 'DELETE' })
}

export function addTrackToPlaylist(playlistId: string, trackId: string) {
  return fetchJson<{ ok: boolean }>(`/api/playlists/${playlistId}/tracks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ track_id: trackId }),
  })
}
