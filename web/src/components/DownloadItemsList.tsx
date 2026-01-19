import { Pause, PauseCircle, Play, PlayCircle } from 'lucide-react'
import type { DownloadItem } from '../types'
import { downloadItemStatusText } from '../utils'

interface Props {
  items: DownloadItem[]
  paused: boolean
  pauseLoading: boolean
  isRunning: boolean
  onPauseAll: () => void
  onPauseItem: (index: number, isPaused: boolean) => void
}

export function DownloadItemsList({
  items,
  paused,
  pauseLoading,
  isRunning,
  onPauseAll,
  onPauseItem,
}: Props) {
  if (!items.length) return null

  const doneCount = items.filter((i) => i.status === 'done').length

  return (
    <div className="download-items-section">
      <div className="download-items-header">
        <span>下载队列</span>
        <div className="download-items-actions">
          <button
            type="button"
            className={`btn btn-sm ${paused ? 'btn-success' : 'btn-secondary'}`}
            disabled={pauseLoading || !isRunning}
            onClick={onPauseAll}
          >
            {paused ? <PlayCircle size={14} /> : <PauseCircle size={14} />}
            <span>{paused ? '继续全部' : '暂停全部'}</span>
          </button>
          <span className="muted">
            {doneCount}/{items.length}
          </span>
        </div>
      </div>
      <div className="download-items-list">
        {items.map((it) => {
          // 显示进度条：下载中或已完成
          const showProgress = it.status === 'downloading' || it.status === 'done'
          const canPause = it.status === 'pending' || it.status === 'paused'
          const isPaused = it.status === 'paused'
          const progress = it.status === 'done' ? 100 : (it.progress || 0)

          return (
            <div key={`${it.index}-${it.url}`} className={`download-item ${it.status}`}>
              <img
                className="download-item-cover"
                src={it.thumbnail || ''}
                alt=""
                onError={(e) => {
                  ;(e.target as HTMLImageElement).style.display = 'none'
                }}
              />
              <div className="download-item-index">{it.index}</div>
              <div className="download-item-info">
                <div className="download-item-title">{it.title}</div>
                {showProgress && (
                  <div className="download-item-progress">
                    <div
                      className="download-item-progress-bar"
                      style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
                    />
                  </div>
                )}
              </div>
              <span className="download-item-status">
                {downloadItemStatusText(it.status, it.progress)}
              </span>
              {canPause && (
                <button
                  type="button"
                  className="download-item-action"
                  onClick={() => onPauseItem(it.index, isPaused)}
                  title={isPaused ? '继续' : '暂停'}
                >
                  {isPaused ? <Play size={14} /> : <Pause size={14} />}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
