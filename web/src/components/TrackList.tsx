import { useEffect, useRef } from 'react'
import { ListPlus, Music, Trash2 } from 'lucide-react'
import type { Track } from '../types'
import { formatBytes, formatDuration } from '../utils'
import { CoverImage } from './CoverImage'

interface Props {
  tracks: Track[]
  playingId: string | null
  onPlay: (track: Track) => void
  onDelete: (trackId: string) => void
  onAddToPlaylist?: (trackId: string) => void
  emptyMessage?: string
  scrollToTrackId?: string | null
}

export function TrackList({ tracks, playingId, onPlay, onDelete, onAddToPlaylist, emptyMessage, scrollToTrackId }: Props) {
  const trackRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  useEffect(() => {
    if (scrollToTrackId) {
      const el = trackRefs.current.get(scrollToTrackId)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }, [scrollToTrackId])
  if (tracks.length === 0) {
    return (
      <div className="track-list-empty">
        <Music size={32} />
        <p>{emptyMessage || '暂无曲目'}</p>
      </div>
    )
  }

  return (
    <div className="track-list">
      {tracks.map((t) => {
        const playing = t.id === playingId
        return (
          <div
            key={t.id}
            ref={(el) => {
              if (el) trackRefs.current.set(t.id, el)
              else trackRefs.current.delete(t.id)
            }}
            className={`track-item ${playing ? 'playing' : ''}`}
            onClick={() => onPlay(t)}
          >
            <CoverImage className="track-cover" src={t.cover_url || null} alt="" />
            <div className="track-info">
              <div className="track-title">{t.title}</div>
              <div className="track-duration">
                {formatDuration(t.duration_seconds)}
                {' · '}
                {formatBytes(t.size_bytes)}
              </div>
            </div>
            {playing && <span className="track-status">播放中</span>}
            <div className="track-actions">
              {onAddToPlaylist && (
                <button
                  className="track-btn add-to-playlist"
                  type="button"
                  title="添加到播放列表"
                  onClick={(e) => {
                    e.stopPropagation()
                    onAddToPlaylist(t.id)
                  }}
                >
                  <ListPlus size={16} />
                </button>
              )}
              <button
                className="track-btn delete"
                type="button"
                title="删除"
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete(t.id)
                }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
