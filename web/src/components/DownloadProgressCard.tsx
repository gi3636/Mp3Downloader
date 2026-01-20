import { CheckCircle, Download, Loader } from 'lucide-react'
import type { DownloadItem, JobMeta } from '../types'
import { statusText } from '../utils'
import './DownloadProgressCard.css'

interface DownloadProgressCardProps {
  jobMeta: JobMeta | null
  jobStatus: string
  jobProgress: number
  jobPaused: boolean
  downloadItems: DownloadItem[]
}

export function DownloadProgressCard({
  jobMeta,
  jobStatus,
  jobProgress,
  jobPaused,
  downloadItems,
}: DownloadProgressCardProps) {
  const items = downloadItems || []
  const doneCount = items.filter((i) => i.status === 'done').length
  const downloadingItem = items.find((i) => i.status === 'downloading')
  const totalCount = items.length

  return (
    <div className="download-progress-card">
      {/* 专辑信息区域 */}
      <div className="download-progress-header">
        {jobMeta?.thumbnail_url ? (
          <img src={jobMeta.thumbnail_url} alt="封面" className="download-progress-cover" />
        ) : (
          <div className="download-progress-cover-placeholder">
            <Download size={24} />
          </div>
        )}
        <div className="download-progress-info">
          <h3 className="download-progress-title">{jobMeta?.title || '正在下载...'}</h3>
          <p className="download-progress-status">
            {jobPaused ? '已暂停' : statusText(jobStatus)}
            {jobMeta?.total_items ? ` · ${jobMeta.total_items} 首曲目` : ''}
          </p>
        </div>
        <div className="download-progress-stats">
          <CheckCircle size={16} />
          <span>{doneCount} / {totalCount || '?'}</span>
        </div>
      </div>
      
      {/* 进度条 */}
      <div className="download-progress-bar-wrapper">
        <div className="download-progress-bar">
          <div className="download-progress-fill" style={{ width: `${jobProgress}%` }} />
        </div>
        <span className="download-progress-pct">{jobProgress.toFixed(0)}%</span>
      </div>
      
      {/* 当前下载项 */}
      {downloadingItem && (
        <div className="download-progress-current">
          <Loader className="spin" size={14} />
          <span>{downloadingItem.title}</span>
        </div>
      )}
    </div>
  )
}
