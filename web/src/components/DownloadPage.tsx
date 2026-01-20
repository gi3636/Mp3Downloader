import type { ChangeEvent } from 'react'
import { Download, FolderDown, ListMusic, Loader, Trash2, X } from 'lucide-react'
import type { DownloadItem, JobMeta } from '../types'
import { statusText } from '../utils'
import { DownloadItemsList } from './DownloadItemsList'

interface DownloadPageProps {
  urlInput: string
  onUrlChange: (value: string) => void
  onStart: () => void
  startLoading: boolean
  isRunning: boolean
  jobMeta: JobMeta | null
  jobStatus: string
  jobProgress: number
  currentJobId: string | null
  jobDownloadUrl: string | null
  jobDownloadItems: DownloadItem[]
  jobPaused: boolean
  pauseLoading: boolean
  cancelLoading: boolean
  deleteLoading: boolean
  onCancel: () => void
  onDelete: () => void
  onPauseResume: () => void
  onPauseItem: (index: number, isPaused: boolean) => void
}

export function DownloadPage({
  urlInput,
  onUrlChange,
  onStart,
  startLoading,
  isRunning,
  jobMeta,
  jobStatus,
  jobProgress,
  currentJobId,
  jobDownloadUrl,
  jobDownloadItems,
  jobPaused,
  pauseLoading,
  cancelLoading,
  deleteLoading,
  onCancel,
  onDelete,
  onPauseResume,
  onPauseItem,
}: DownloadPageProps) {
  const albumHasAny = Boolean(jobMeta?.title || jobMeta?.thumbnail_url || jobMeta?.total_items)

  return (
    <div className="download-page">
      <div className="input-row">
        <input
          type="text"
          className="url-input"
          placeholder="输入 YouTube 链接..."
          value={urlInput}
          onChange={(e: ChangeEvent<HTMLInputElement>) => onUrlChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onStart()}
        />
        <button
          className="btn btn-primary"
          onClick={onStart}
          disabled={startLoading || isRunning}
        >
          {startLoading ? <Loader className="spin" size={16} /> : <Download size={16} />}
          {startLoading ? '解析中...' : '开始下载'}
        </button>
      </div>

      {/* 专辑信息 */}
      {albumHasAny && (
        <div className="album-info">
          {jobMeta?.thumbnail_url && (
            <img src={jobMeta.thumbnail_url} alt="封面" className="album-cover" />
          )}
          <div className="album-details">
            <h3>{jobMeta?.title || '未知专辑'}</h3>
            {jobMeta?.total_items && <p>{jobMeta.total_items} 首曲目</p>}
            <p className="status-text">{statusText(jobStatus)}</p>
          </div>
        </div>
      )}

      {/* 进度条 */}
      {isRunning && (
        <div className="progress-section">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${jobProgress}%` }} />
          </div>
          <span className="progress-text">{jobProgress.toFixed(0)}%</span>
        </div>
      )}

      {/* 操作按钮 */}
      {currentJobId && (
        <div className="action-buttons">
          {isRunning && (
            <button
              className="btn btn-danger"
              onClick={onCancel}
              disabled={cancelLoading}
            >
              {cancelLoading ? <Loader className="spin" size={16} /> : <X size={16} />}
              取消
            </button>
          )}
          {jobDownloadUrl && (
            <a href={jobDownloadUrl} className="btn btn-success" download>
              <FolderDown size={16} />
              下载 ZIP
            </a>
          )}
          {!isRunning && (
            <button
              className="btn btn-danger"
              onClick={onDelete}
              disabled={deleteLoading}
            >
              {deleteLoading ? <Loader className="spin" size={16} /> : <Trash2 size={16} />}
              删除任务
            </button>
          )}
        </div>
      )}

      {/* 下载队列 */}
      {jobDownloadItems.length > 0 && (
        <div className="download-queue">
          <h4>
            <ListMusic size={16} />
            下载队列
          </h4>
          <DownloadItemsList
            items={jobDownloadItems}
            paused={jobPaused}
            pauseLoading={pauseLoading}
            isRunning={isRunning}
            onPauseAll={onPauseResume}
            onPauseItem={onPauseItem}
          />
        </div>
      )}
    </div>
  )
}
