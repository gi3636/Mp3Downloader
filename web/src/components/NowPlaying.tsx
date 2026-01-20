import { Trash2 } from 'lucide-react'
import type { Track } from '../types'
import { formatDuration } from '../utils'
import { CoverImage } from './CoverImage'

interface Props {
  track: Track | null
  currentIndex: number
  totalCount: number
  onClickTitle?: () => void
  onDelete?: () => void
}

export function NowPlaying({ track, currentIndex, totalCount, onClickTitle, onDelete }: Props) {
  if (!track) return null

  return (
    <div className="now-playing">
      <CoverImage className="now-playing-cover" src={track.cover_url || null} alt="" />
      <div className="now-playing-info">
        <div 
          className="now-playing-title" 
          onClick={onClickTitle}
          style={{ cursor: onClickTitle ? 'pointer' : 'default' }}
          title={onClickTitle ? '点击查看音乐库' : undefined}
        >
          {track.title}
        </div>
        <div className="now-playing-meta">
          <span className="now-playing-duration">{formatDuration(track.duration_seconds)}</span>
          <span className="now-playing-index">
            {currentIndex + 1} / {totalCount}
          </span>
        </div>
      </div>
      {onDelete && (
        <button
          className="now-playing-delete"
          type="button"
          title="删除当前歌曲"
          onClick={onDelete}
        >
          <Trash2 size={16} />
        </button>
      )}
    </div>
  )
}
