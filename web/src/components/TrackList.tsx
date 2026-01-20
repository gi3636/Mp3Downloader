import { Trash2 } from 'lucide-react'
import type { Track } from '../types'
import { formatBytes, formatDuration } from '../utils'
import { CoverImage } from './CoverImage'

interface Props {
  tracks: Track[]
  playingId: string | null
  onPlay: (track: Track) => void
  onDelete: (trackId: string) => void
}

export function TrackList({ tracks, playingId, onPlay, onDelete }: Props) {
  return (
    <div className="track-list">
      {tracks.map((t) => {
        const playing = t.id === playingId
        return (
          <div
            key={t.id}
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
