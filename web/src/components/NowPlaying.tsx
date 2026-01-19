import type { Track } from '../types'
import { formatDuration } from '../utils'

interface Props {
  track: Track | null
  currentIndex: number
  totalCount: number
}

export function NowPlaying({ track, currentIndex, totalCount }: Props) {
  if (!track) return null

  return (
    <div className="now-playing">
      <img
        className="now-playing-cover"
        alt=""
        src={track.cover_url || ''}
        onError={(e) => {
          ;(e.target as HTMLImageElement).style.display = 'none'
        }}
      />
      <div className="now-playing-info">
        <div className="now-playing-title">{track.title}</div>
        <div className="now-playing-meta">
          <span className="now-playing-duration">{formatDuration(track.duration_seconds)}</span>
          <span className="now-playing-index">
            {currentIndex + 1} / {totalCount}
          </span>
        </div>
      </div>
    </div>
  )
}
