import { useState, useEffect } from 'react'
import { Check, Edit2, FolderPlus, Merge, Plus, Trash2, X } from 'lucide-react'
import type { Album } from '../api'
import './AlbumManager.css'
import * as api from '../api'
import { CoverImage } from './CoverImage'

interface AlbumManagerProps {
  open: boolean
  onClose: () => void
  onToast: (message: string, type: 'success' | 'error') => void
  onRefresh: () => void
}

export function AlbumManager({ open, onClose, onToast, onRefresh }: AlbumManagerProps) {
  const [albums, setAlbums] = useState<Album[]>([])
  const [loading, setLoading] = useState(false)
  const [newAlbumName, setNewAlbumName] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')
  const [selectedForMerge, setSelectedForMerge] = useState<Set<string>>(new Set())
  const [mergeTarget, setMergeTarget] = useState<string | null>(null)

  const loadAlbums = async () => {
    setLoading(true)
    try {
      const data = await api.getAlbums()
      setAlbums(data.albums || [])
    } catch (e: any) {
      onToast(e?.message || '加载专辑失败', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) {
      loadAlbums()
      setSelectedForMerge(new Set())
      setMergeTarget(null)
    }
  }, [open])

  const handleCreate = async () => {
    if (!newAlbumName.trim()) return
    try {
      await api.createAlbum(newAlbumName.trim())
      setNewAlbumName('')
      onToast('专辑已创建', 'success')
      loadAlbums()
      onRefresh()
    } catch (e: any) {
      onToast(e?.message || '创建失败', 'error')
    }
  }

  const handleRename = async (albumId: string) => {
    if (!editingName.trim()) return
    try {
      await api.renameAlbum(albumId, editingName.trim())
      setEditingId(null)
      onToast('已重命名', 'success')
      loadAlbums()
      onRefresh()
    } catch (e: any) {
      onToast(e?.message || '重命名失败', 'error')
    }
  }

  const handleDelete = async (albumId: string) => {
    if (!confirm(`确定要删除专辑 "${albumId}" 及其所有曲目吗？此操作不可撤销。`)) return
    try {
      await api.deleteAlbum(albumId)
      onToast('专辑已删除', 'success')
      loadAlbums()
      onRefresh()
    } catch (e: any) {
      onToast(e?.message || '删除失败', 'error')
    }
  }

  const toggleMergeSelection = (albumId: string) => {
    const newSet = new Set(selectedForMerge)
    if (newSet.has(albumId)) {
      newSet.delete(albumId)
    } else {
      newSet.add(albumId)
    }
    setSelectedForMerge(newSet)
  }

  const handleMerge = async () => {
    if (!mergeTarget || selectedForMerge.size === 0) return
    const sourceIds = Array.from(selectedForMerge).filter(id => id !== mergeTarget)
    if (sourceIds.length === 0) {
      onToast('请选择要合并的源专辑', 'error')
      return
    }
    try {
      const result = await api.mergeAlbums(mergeTarget, sourceIds)
      onToast(`已合并 ${result.merged_count} 首曲目`, 'success')
      setSelectedForMerge(new Set())
      setMergeTarget(null)
      loadAlbums()
      onRefresh()
    } catch (e: any) {
      onToast(e?.message || '合并失败', 'error')
    }
  }

  if (!open) return null

  const isMergeMode = mergeTarget !== null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content album-manager" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{isMergeMode ? '合并专辑' : '专辑管理'}</h3>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {isMergeMode ? (
          <div className="merge-mode">
            <p className="merge-hint">
              选择要合并到 <strong>{mergeTarget}</strong> 的专辑：
            </p>
            <div className="album-list">
              {albums.filter(a => a.id !== mergeTarget).map((album) => (
                <div
                  key={album.id}
                  className={`album-item selectable ${selectedForMerge.has(album.id) ? 'selected' : ''}`}
                  onClick={() => toggleMergeSelection(album.id)}
                >
                  <CoverImage className="album-cover" src={album.cover_url} alt="" />
                  <div className="album-info">
                    <div className="album-name">{album.name}</div>
                    <div className="album-count">{album.track_count} 首</div>
                  </div>
                  {selectedForMerge.has(album.id) && (
                    <Check size={18} className="check-icon" />
                  )}
                </div>
              ))}
            </div>
            <div className="merge-actions">
              <button className="btn btn-secondary" onClick={() => setMergeTarget(null)}>
                取消
              </button>
              <button
                className="btn btn-primary"
                onClick={handleMerge}
                disabled={selectedForMerge.size === 0}
              >
                <Merge size={16} />
                合并 {selectedForMerge.size} 个专辑
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="create-album-row">
              <input
                type="text"
                placeholder="新专辑名称..."
                value={newAlbumName}
                onChange={(e) => setNewAlbumName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              />
              <button
                className="btn btn-primary btn-sm"
                onClick={handleCreate}
                disabled={!newAlbumName.trim()}
              >
                <Plus size={16} />
                创建
              </button>
            </div>

            {loading ? (
              <p className="loading-hint">加载中...</p>
            ) : albums.length === 0 ? (
              <p className="empty-hint">暂无专辑</p>
            ) : (
              <div className="album-list">
                {albums.map((album) => (
                  <div key={album.id} className="album-item">
                    <CoverImage className="album-cover" src={album.cover_url} alt="" />
                    {editingId === album.id ? (
                      <input
                        type="text"
                        className="album-edit-input"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleRename(album.id)
                          if (e.key === 'Escape') setEditingId(null)
                        }}
                        autoFocus
                      />
                    ) : (
                      <div className="album-info">
                        <div className="album-name">{album.name}</div>
                        <div className="album-count">{album.track_count} 首</div>
                      </div>
                    )}
                    <div className="album-actions">
                      {editingId === album.id ? (
                        <>
                          <button
                            className="icon-btn"
                            onClick={() => handleRename(album.id)}
                            title="保存"
                          >
                            <Check size={16} />
                          </button>
                          <button
                            className="icon-btn"
                            onClick={() => setEditingId(null)}
                            title="取消"
                          >
                            <X size={16} />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            className="icon-btn"
                            onClick={() => {
                              setEditingId(album.id)
                              setEditingName(album.name)
                            }}
                            title="重命名"
                          >
                            <Edit2 size={16} />
                          </button>
                          <button
                            className="icon-btn"
                            onClick={() => setMergeTarget(album.id)}
                            title="合并其他专辑到此"
                          >
                            <Merge size={16} />
                          </button>
                          <button
                            className="icon-btn danger"
                            onClick={() => handleDelete(album.id)}
                            title="删除"
                          >
                            <Trash2 size={16} />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
