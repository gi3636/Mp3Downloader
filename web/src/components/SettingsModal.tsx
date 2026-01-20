import { useState, useEffect } from 'react'
import { X, FolderOpen, Save, Loader, ArrowRight, ExternalLink } from 'lucide-react'
import * as api from '../api'

// 检测是否在 Tauri 环境中
const isTauri = typeof window !== 'undefined' && '__TAURI__' in window

// 动态导入 Tauri dialog
async function openFolderDialog(): Promise<string | null> {
  if (!isTauri) return null
  try {
    const { open } = await import('@tauri-apps/plugin-dialog')
    const selected = await open({
      directory: true,
      multiple: false,
      title: '选择下载目录',
    })
    return selected as string | null
  } catch (e) {
    console.error('Tauri dialog error:', e)
    return null
  }
}

interface SettingsModalProps {
  open: boolean
  onClose: () => void
  onToast: (message: string, type?: 'success' | 'error' | 'info') => void
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

export function SettingsModal({ open, onClose, onToast }: SettingsModalProps) {
  const [downloadDir, setDownloadDir] = useState('')
  const [originalDir, setOriginalDir] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  
  // 迁移确认弹窗状态
  const [migrationConfirmOpen, setMigrationConfirmOpen] = useState(false)
  const [migrationInfo, setMigrationInfo] = useState<api.MigrationCheck | null>(null)
  const [migrating, setMigrating] = useState(false)
  const [deleteSource, setDeleteSource] = useState(true)

  useEffect(() => {
    if (open) {
      loadSettings()
      setMigrationConfirmOpen(false)
      setMigrationInfo(null)
    }
  }, [open])

  const loadSettings = async () => {
    setLoading(true)
    try {
      const settings = await api.getSettings()
      setDownloadDir(settings.download_dir || '')
      setOriginalDir(settings.download_dir || '')
    } catch (e: any) {
      onToast(e.message || '加载设置失败', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!downloadDir.trim()) {
      onToast('下载目录不能为空', 'error')
      return
    }

    // 如果目录没有变化，直接保存
    if (downloadDir.trim() === originalDir) {
      onToast('设置已保存', 'success')
      onClose()
      return
    }

    // 检查是否需要迁移
    setSaving(true)
    try {
      const check = await api.checkMigration(downloadDir.trim())
      if (check.need_migration) {
        setMigrationInfo(check)
        setMigrationConfirmOpen(true)
        setSaving(false)
        return
      }
      
      // 不需要迁移，直接保存
      await api.saveSettings({ download_dir: downloadDir.trim() })
      onToast('设置已保存', 'success')
      onClose()
    } catch (e: any) {
      onToast(e.message || '保存设置失败', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleMigrate = async (shouldMigrate: boolean) => {
    if (!migrationInfo) return

    setMigrating(true)
    try {
      if (shouldMigrate) {
        const result = await api.migrateFiles(downloadDir.trim(), deleteSource)
        if (result.ok) {
          const action = deleteSource ? '迁移' : '复制'
          onToast(`已${action} ${result.migrated_count} 个项目`, 'success')
        }
      }
      
      // 保存新设置
      await api.saveSettings({ download_dir: downloadDir.trim() })
      onToast('设置已保存', 'success')
      setMigrationConfirmOpen(false)
      onClose()
    } catch (e: any) {
      onToast(e.message || '迁移失败', 'error')
    } finally {
      setMigrating(false)
    }
  }

  if (!open) return null

  return (
    <div className={`modal ${open ? 'visible' : ''}`}>
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal-content" style={{ maxWidth: '480px' }}>
        <div className="modal-header">
          <h3 className="modal-title">设置</h3>
          <button className="modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
              <Loader size={24} className="spin" />
            </div>
          ) : (
            <div className="settings-form">
              <div className="form-group">
                <label className="form-label">下载目录</label>
                <div className="input-row">
                  <input
                    type="text"
                    className="form-input"
                    value={downloadDir}
                    onChange={(e) => setDownloadDir(e.target.value)}
                    placeholder="~/Downloads/Mp3Downloader"
                  />
                  <button
                    className="btn btn-secondary"
                    onClick={async () => {
                      if (isTauri) {
                        const selected = await openFolderDialog()
                        if (selected) {
                          setDownloadDir(selected)
                        }
                      } else {
                        onToast('在浏览器中请直接输入路径', 'info')
                      }
                    }}
                    title={isTauri ? '选择文件夹' : '浏览器不支持，请手动输入'}
                  >
                    <FolderOpen size={16} />
                  </button>
                </div>
                <p className="form-hint">下载的音乐文件将保存到此目录</p>
                <button
                  className="btn btn-secondary"
                  style={{ marginTop: '12px' }}
                  onClick={async () => {
                    try {
                      await api.openDownloadFolder()
                    } catch (e: any) {
                      onToast(e.message || '打开目录失败', 'error')
                    }
                  }}
                >
                  <ExternalLink size={16} />
                  打开下载目录
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            取消
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving || loading}
          >
            {saving ? <Loader size={16} className="spin" /> : <Save size={16} />}
            保存
          </button>
        </div>
      </div>

      {/* 迁移确认弹窗 */}
      {migrationConfirmOpen && migrationInfo && (
        <div className="modal visible" style={{ zIndex: 60 }}>
          <div className="modal-backdrop" />
          <div className="modal-content" style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h3 className="modal-title">迁移已下载的文件？</h3>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom: '16px', color: 'var(--text-secondary)' }}>
                检测到旧目录中有 <span style={{ color: 'var(--accent)' }}>{migrationInfo.file_count}</span> 个文件
                （共 <span style={{ color: 'var(--accent)' }}>{formatSize(migrationInfo.total_size)}</span>）
              </p>
              <div className="migration-paths">
                <div className="migration-path old">{migrationInfo.old_dir}</div>
                <ArrowRight size={16} style={{ margin: '8px auto', display: 'block', color: 'var(--muted)' }} />
                <div className="migration-path new">{migrationInfo.new_dir}</div>
              </div>
              <label className="checkbox-row" style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={deleteSource}
                  onChange={(e) => setDeleteSource(e.target.checked)}
                  style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                />
                <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                  删除原文件夹（不勾选则为复制）
                </span>
              </label>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => handleMigrate(false)}
                disabled={migrating}
              >
                不迁移
              </button>
              <button
                className="btn btn-primary"
                onClick={() => handleMigrate(true)}
                disabled={migrating}
              >
                {migrating ? <Loader size={16} className="spin" /> : <ArrowRight size={16} />}
                迁移文件
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
