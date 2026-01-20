import type { CreateJobResponse, JobResponse, ResolveResponse, TracksResponse } from './types'

async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(input, init)
  } catch (e) {
    console.error('Network error:', e)
    throw new Error('网络连接失败，请检查后端服务是否运行')
  }
  
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = (data as any)?.error || (data as any)?.message || 'Request failed'
    const err = new Error(msg) as any
    err.status = res.status
    err.data = data
    throw err
  }
  return data as T
}

export function resolveUrl(url: string) {
  return fetchJson<ResolveResponse>('/api/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
}

export function createJob(body: { url: string; video_urls?: string[]; video_titles?: string[]; video_thumbnails?: string[] }) {
  return fetchJson<CreateJobResponse>('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function getJob(jobId: string) {
  return fetchJson<JobResponse>(`/api/jobs/${jobId}`)
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
