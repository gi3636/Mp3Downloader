import { Music, Pause, Play, Shuffle, SkipBack, SkipForward, Trash2 } from 'lucide-react'
import type { Track } from '../types'
import './PlayerControls.css'
import { formatDuration } from '../utils'
import { CoverImage } from './CoverImage'

interface Props {
  track: Track | null
  currentIndex: number
  totalCount: number
  isPlaying: boolean
  shuffle: boolean
  currentTime: number
  duration: number
  seeking: boolean
  seekTime: number
  onPlayPause: () => void
  onPrev: () => void
  onNext: () => void
  onToggleShuffle: () => void
  onSeekChange: (time: number) => void
  onSeekCommit: (time: number) => void
  onClickTitle?: () => void
  onDelete?: () => void
}

export function PlayerControls({
  track,
  currentIndex,
  totalCount,
  isPlaying,
  shuffle,
  currentTime,
  duration,
  seeking,
  seekTime,
  onPlayPause,
  onPrev,
  onNext,
  onToggleShuffle,
  onSeekChange,
  onSeekCommit,
  onClickTitle,
  onDelete,
}: Props) {
  const safeDuration = Number.isFinite(duration) && duration > 0 ? duration : 0
  const displayTime = seeking ? seekTime : currentTime
  const pct = safeDuration > 0 ? Math.max(0, Math.min(100, (displayTime / safeDuration) * 100)) : 0

  return (
    <div className="player-bar">
      {/* 歌曲信息 + 播放控件 */}
      <div className="player-main">
        {track ? (
          <>
            <CoverImage className="player-track-cover" src={track.cover_url || null} alt="" />
            <div className="player-track-info">
              <div 
                className="player-track-title" 
                onClick={onClickTitle}
                style={{ cursor: onClickTitle ? 'pointer' : 'default' }}
                title={onClickTitle ? '点击查看音乐库' : undefined}
              >
                {track.title}
              </div>
              <div className="player-track-meta">
                {currentIndex + 1} / {totalCount}
              </div>
            </div>
          </>
        ) : (
          <div className="player-track-empty">
            <Music size={20} />
            <span>选择一首歌曲开始播放</span>
          </div>
        )}

        {/* 播放控件 */}
        <div className="player-controls">
          <button className="player-btn" type="button" title="上一首" onClick={onPrev}>
            <SkipBack size={18} />
          </button>
          <button className="player-btn play-btn" type="button" title="播放/暂停" onClick={onPlayPause}>
            {isPlaying ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <button className="player-btn" type="button" title="下一首" onClick={onNext}>
            <SkipForward size={18} />
          </button>
          <button
            className={`player-btn ${shuffle ? 'active' : ''}`}
            type="button"
            title="随机播放"
            onClick={onToggleShuffle}
          >
            <Shuffle size={18} />
          </button>
          {track && onDelete && (
            <button
              className="player-btn delete-btn"
              type="button"
              title="删除当前歌曲"
              onClick={onDelete}
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>

      {/* 进度条 */}
      <div className="player-progress">
        <span className="player-time">{formatDuration(displayTime)}</span>
        <input
          className="player-range"
          type="range"
          min={0}
          max={safeDuration}
          step={0.1}
          value={Math.min(displayTime, safeDuration)}
          disabled={safeDuration <= 0}
          style={{
            background: `linear-gradient(90deg, var(--accent) 0%, var(--accent) ${pct}%, rgba(255,255,255,0.18) ${pct}%, rgba(255,255,255,0.18) 100%)`,
          }}
          onChange={(e) => onSeekChange(Number(e.target.value))}
          onMouseUp={() => onSeekCommit(seekTime)}
          onTouchEnd={() => onSeekCommit(seekTime)}
        />
        <span className="player-time">{formatDuration(safeDuration)}</span>
      </div>
    </div>
  )
}
