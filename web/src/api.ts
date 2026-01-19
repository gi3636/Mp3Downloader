import type { CreateJobResponse, JobResponse, ResolveResponse, TracksResponse } from './types'

async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = (data as any)?.error || (data as any)?.message || 'Request failed'
    throw new Error(msg)
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
