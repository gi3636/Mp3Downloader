import { CheckCircle, Clock, Download, FolderOpen, Loader, Pause, StopCircle, Trash2, XCircle } from 'lucide-react'
import type { JobListItem } from '../api'
import { CoverImage } from './CoverImage'

interface Props {
  jobs: JobListItem[]
  currentJobId: string | null
  onSelectJob: (jobId: string) => void
  onDeleteJob: (jobId: string) => void
  onOpenFolder: (jobId: string) => void
  onCancelJob: (jobId: string) => void
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  
  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins} 分钟前`
  
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours} 小时前`
  
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays} 天前`
  
  return date.toLocaleDateString()
}

function getStatusIcon(status: string, paused: boolean) {
  if (paused) return <Pause size={14} />
  switch (status) {
    case 'running':
    case 'queued':
      return <Loader className="spin" size={14} />
    case 'done':
      return <CheckCircle size={14} />
    case 'error':
      return <XCircle size={14} />
    case 'canceled':
      return <XCircle size={14} />
    default:
      return <Clock size={14} />
  }
}

function getStatusText(status: string, paused: boolean): string {
  if (paused) return '已暂停'
  switch (status) {
    case 'running': return '下载中'
    case 'queued': return '排队中'
    case 'done': return '已完成'
    case 'error': return '失败'
    case 'canceled': return '已取消'
    default: return status
  }
}

export function JobList({ jobs, currentJobId, onSelectJob, onDeleteJob, onOpenFolder, onCancelJob }: Props) {
  const jobList = jobs || []
  const runningJobs = jobList.filter(j => ['running', 'queued'].includes(j.status) || j.paused)
  const completedJobs = jobList.filter(j => ['done', 'error', 'canceled'].includes(j.status) && !j.paused)
  
  if (jobList.length === 0) {
    return null
  }

  return (
    <div className="job-list-section">
      {/* 下载中 */}
      {runningJobs.length > 0 && (
        <div className="job-list-group">
          <h4 className="job-list-title">
            <Download size={16} />
            下载中 ({runningJobs.length})
          </h4>
          <div className="job-list">
            {runningJobs.map(job => (
              <div
                key={job.id}
                className={`job-item ${job.id === currentJobId ? 'active' : ''} ${job.status}`}
                onClick={() => onSelectJob(job.id)}
              >
                <CoverImage
                  className="job-item-cover"
                  src={job.meta.thumbnail_url}
                  alt=""
                />
                <div className="job-item-info">
                  <div className="job-item-title">
                    {job.meta.title || '未知标题'}
                  </div>
                  <div className="job-item-meta">
                    <span className={`job-item-status ${job.status}`}>
                      {getStatusIcon(job.status, job.paused)}
                      {getStatusText(job.status, job.paused)}
                    </span>
                    {job.status === 'running' && (
                      <span className="job-item-progress">{job.progress.toFixed(0)}%</span>
                    )}
                  </div>
                </div>
                <div className="job-item-actions">
                  {job.status === 'running' && (
                    <button
                      className="job-item-action job-item-cancel"
                      onClick={(e) => {
                        e.stopPropagation()
                        onCancelJob(job.id)
                      }}
                      title="取消下载"
                    >
                      <StopCircle size={14} />
                    </button>
                  )}
                  <button
                    className="job-item-action"
                    onClick={(e) => {
                      e.stopPropagation()
                      onOpenFolder(job.id)
                    }}
                    title="打开文件夹"
                  >
                    <FolderOpen size={14} />
                  </button>
                  <button
                    className="job-item-action job-item-delete"
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteJob(job.id)
                    }}
                    title="删除任务"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 已完成 */}
      {completedJobs.length > 0 && (
        <div className="job-list-group">
          <h4 className="job-list-title">
            <CheckCircle size={16} />
            已完成 ({completedJobs.length})
          </h4>
          <div className="job-list">
            {completedJobs.map(job => (
              <div
                key={job.id}
                className={`job-item ${job.id === currentJobId ? 'active' : ''} ${job.status}`}
                onClick={() => onSelectJob(job.id)}
              >
                <CoverImage
                  className="job-item-cover"
                  src={job.meta.thumbnail_url}
                  alt=""
                />
                <div className="job-item-info">
                  <div className="job-item-title">
                    {job.meta.title || '未知标题'}
                  </div>
                  <div className="job-item-meta">
                    <span className={`job-item-status ${job.status}`}>
                      {getStatusIcon(job.status, false)}
                      {getStatusText(job.status, false)}
                    </span>
                    <span className="job-item-time">{formatTime(job.created_at)}</span>
                  </div>
                </div>
                <div className="job-item-actions">
                  <button
                    className="job-item-action"
                    onClick={(e) => {
                      e.stopPropagation()
                      onOpenFolder(job.id)
                    }}
                    title="打开文件夹"
                  >
                    <FolderOpen size={14} />
                  </button>
                  <button
                    className="job-item-action job-item-delete"
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteJob(job.id)
                    }}
                    title="删除任务"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
