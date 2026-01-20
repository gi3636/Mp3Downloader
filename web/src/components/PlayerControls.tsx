import { Pause, Play, Shuffle, SkipBack, SkipForward, Volume2, VolumeX } from 'lucide-react'
import { formatDuration } from '../utils'

interface Props {
  isPlaying: boolean
  shuffle: boolean
  currentTime: number
  duration: number
  seeking: boolean
  seekTime: number
  volume: number
  muted: boolean
  onPlayPause: () => void
  onPrev: () => void
  onNext: () => void
  onToggleShuffle: () => void
  onSeekChange: (time: number) => void
  onSeekCommit: (time: number) => void
  onVolumeChange: (volume: number) => void
  onToggleMute: () => void
}

export function PlayerControls({
  isPlaying,
  shuffle,
  currentTime,
  duration,
  seeking,
  seekTime,
  volume,
  muted,
  onPlayPause,
  onPrev,
  onNext,
  onToggleShuffle,
  onSeekChange,
  onSeekCommit,
  onVolumeChange,
  onToggleMute,
}: Props) {
  const safeDuration = Number.isFinite(duration) && duration > 0 ? duration : 0
  const displayTime = seeking ? seekTime : currentTime
  const pct = safeDuration > 0 ? Math.max(0, Math.min(100, (displayTime / safeDuration) * 100)) : 0
  const volumePct = muted ? 0 : volume * 100

  return (
    <div className="player-bar">
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
      </div>

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

      <div className="player-volume">
        <button className="player-btn" type="button" title={muted ? '取消静音' : '静音'} onClick={onToggleMute}>
          {muted || volume === 0 ? <VolumeX size={18} /> : <Volume2 size={18} />}
        </button>
        <input
          className="volume-range"
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={muted ? 0 : volume}
          style={{
            background: `linear-gradient(90deg, var(--accent) 0%, var(--accent) ${volumePct}%, rgba(255,255,255,0.18) ${volumePct}%, rgba(255,255,255,0.18) 100%)`,
          }}
          onChange={(e) => onVolumeChange(Number(e.target.value))}
        />
      </div>
    </div>
  )
}
