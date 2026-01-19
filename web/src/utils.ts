// 格式化时长 (秒 -> mm:ss)
export function formatDuration(seconds?: number | null): string {
  if (typeof seconds !== 'number' || Number.isNaN(seconds)) return '--:--'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

// 状态文本映射
export function statusText(status: string): string {
  const map: Record<string, string> = {
    queued: '排队中',
    running: '下载中',
    done: '已完成',
    error: '出错',
    canceled: '已取消',
    canceling: '取消中',
  }
  return map[status] || status || '-'
}

// 下载项状态文本
export function downloadItemStatusText(status: string, progress?: number): string {
  const map: Record<string, string> = {
    pending: '等待中',
    downloading: `${Math.round(progress || 0)}%`,
    done: '完成',
    error: '失败',
    skipped: '跳过',
    paused: '已暂停',
  }
  return map[status] || status
}

// 格式化文件大小 (bytes -> KB/MB/GB)
export function formatBytes(bytes?: number | null): string {
  if (typeof bytes !== 'number' || Number.isNaN(bytes) || bytes <= 0) return '--'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = bytes
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  const digits = i === 0 ? 0 : i === 1 ? 1 : 2
  return `${v.toFixed(digits)} ${units[i]}`
}
