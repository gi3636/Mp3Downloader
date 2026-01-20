import { useState, type ChangeEvent } from 'react'
import { Check, Edit2, FolderOpen, FolderPlus, Library, Loader, Merge, Music, Plus, Search, Sparkles, Trash2, X } from 'lucide-react'
import type { Track } from '../types'
import './LibraryPage.css'
import type { Playlist } from '../api'
import * as api from '../api'
import { TrackList } from './TrackList'
import { PlaylistPicker } from './PlaylistPicker'

export type SortMode = 'created_desc' | 'created_asc' | 'alpha_asc' | 'alpha_desc' | 'album'

export interface AlbumGroup {
  name: string
  cover: string | null
  tracks: Track[]
}

interface LibraryPageProps {
  loading?: boolean
  search: string
  onSearchChange: (value: string) => void
  sortMode: SortMode
  onSortModeChange: (mode: SortMode) => void
  sortedTracks: Track[]
  albumGroups: AlbumGroup[]
  currentPlaylist: Track[]
  selectedAlbum: string | null
  onSelectAlbum: (album: string) => void
  playingTrackId: string | null
  onPlayTrack: (track: Track) => void
  onDeleteTrack: (trackId: string) => void
  scrollToTrackId?: string | null
  playlists?: Playlist[]
  onCreatePlaylist?: (name: string) => void
  onAddToPlaylist?: (playlistId: string, trackId: string) => void
  onRefreshPlaylists?: () => void
  onOpenAlbumManager?: () => void
  onRemoveFromAlbum?: (albumId: string, trackId: string) => void
  onOpenAIClassify?: () => void
}

export function LibraryPage({
  loading = false,
  search,
  onSearchChange,
  sortMode,
  onSortModeChange,
  sortedTracks,
  albumGroups,
  currentPlaylist,
  selectedAlbum,
  onSelectAlbum,
  playingTrackId,
  onPlayTrack,
  onDeleteTrack,
  scrollToTrackId,
  playlists,
  onCreatePlaylist,
  onAddToPlaylist,
  onRefreshPlaylists,
  onOpenAlbumManager,
  onRemoveFromAlbum,
  onOpenAIClassify,
}: LibraryPageProps) {
  const hasPlaylistFeature = playlists && onCreatePlaylist && onAddToPlaylist && onRefreshPlaylists
  const [showPlaylistPicker, setShowPlaylistPicker] = useState(false)
  const [pendingTrackId, setPendingTrackId] = useState<string | null>(null)
  
  // 专辑管理状态
  const [editingAlbum, setEditingAlbum] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')
  const [newAlbumName, setNewAlbumName] = useState('')
  const [showNewAlbumInput, setShowNewAlbumInput] = useState(false)
  const [mergeTarget, setMergeTarget] = useState<string | null>(null)
  const [mergeSelected, setMergeSelected] = useState<Set<string>>(new Set())

  const handleAddToPlaylist = (trackId: string) => {
    if (!hasPlaylistFeature) return
    setPendingTrackId(trackId)
    setShowPlaylistPicker(true)
    onRefreshPlaylists!()
  }

  const handleSelectPlaylist = (playlistId: string) => {
    if (pendingTrackId && onAddToPlaylist) {
      onAddToPlaylist(playlistId, pendingTrackId)
    }
    setShowPlaylistPicker(false)
    setPendingTrackId(null)
  }

  const handleClosePicker = () => {
    setShowPlaylistPicker(false)
    setPendingTrackId(null)
  }

  // 专辑管理处理函数
  const handleCreateAlbum = async () => {
    if (!newAlbumName.trim()) return
    try {
      await api.createAlbum(newAlbumName.trim())
      setNewAlbumName('')
      setShowNewAlbumInput(false)
      // 触发刷新 - 通过调用 onOpenAlbumManager 然后立即关闭来刷新
      window.location.reload() // 临时方案，后续可以通过 onRefresh 回调优化
    } catch (e: any) {
      alert(e?.message || '创建失败')
    }
  }

  const handleRenameAlbum = async (oldName: string) => {
    if (!editingName.trim() || editingName === oldName) {
      setEditingAlbum(null)
      return
    }
    try {
      await api.renameAlbum(oldName, editingName.trim())
      setEditingAlbum(null)
      window.location.reload()
    } catch (e: any) {
      alert(e?.message || '重命名失败')
    }
  }

  const handleDeleteAlbum = async (albumName: string) => {
    if (!confirm(`确定要删除专辑 "${albumName}" 及其所有曲目吗？`)) return
    try {
      await api.deleteAlbum(albumName)
      window.location.reload()
    } catch (e: any) {
      alert(e?.message || '删除失败')
    }
  }

  const handleStartMerge = (targetAlbum: string) => {
    setMergeTarget(targetAlbum)
    setMergeSelected(new Set())
  }

  const toggleMergeSelect = (albumName: string) => {
    const newSet = new Set(mergeSelected)
    if (newSet.has(albumName)) {
      newSet.delete(albumName)
    } else {
      newSet.add(albumName)
    }
    setMergeSelected(newSet)
  }

  const handleConfirmMerge = async () => {
    if (!mergeTarget || mergeSelected.size === 0) return
    try {
      await api.mergeAlbums(mergeTarget, Array.from(mergeSelected))
      setMergeTarget(null)
      setMergeSelected(new Set())
      window.location.reload()
    } catch (e: any) {
      alert(e?.message || '合并失败')
    }
  }

  const handleCancelMerge = () => {
    setMergeTarget(null)
    setMergeSelected(new Set())
  }

  // 加载状态
  if (loading) {
    return (
      <div className="library-page">
        <div className="library-loading">
          <Loader className="spin" size={32} />
          <p>正在加载音乐库...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="library-page">
      {/* 工具栏 */}
      <div className="library-toolbar">
        <div className="search-box">
          <Search size={16} />
          <input
            type="text"
            placeholder="搜索..."
            value={search}
            onChange={(e: ChangeEvent<HTMLInputElement>) => onSearchChange(e.target.value)}
          />
        </div>
        {search && (
          <span className="search-result-count">
            找到 {sortedTracks.length} 首
          </span>
        )}
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => api.openDownloadFolder()}
          title="打开文件位置"
        >
          <FolderOpen size={16} />
        </button>
        {onOpenAlbumManager && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={onOpenAlbumManager}
            title="专辑管理"
          >
            <FolderPlus size={16} />
          </button>
        )}
        {onOpenAIClassify && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={onOpenAIClassify}
            title="AI 智能分类"
          >
            <Sparkles size={16} />
          </button>
        )}
        <select
          className="sort-select"
          value={sortMode}
          onChange={(e: ChangeEvent<HTMLSelectElement>) =>
            onSortModeChange(e.target.value as SortMode)
          }
        >
          <option value="created_desc">最新添加</option>
          <option value="created_asc">最早添加</option>
          <option value="alpha_asc">A-Z</option>
          <option value="alpha_desc">Z-A</option>
          <option value="album">按专辑</option>
        </select>
      </div>

      {/* 专辑模式布局 */}
      {sortMode === 'album' ? (
        <div className="album-layout">
          {/* 左侧曲目列表 */}
          <div className="album-tracks-panel">
            {selectedAlbum ? (
              <>
                <h4 className="album-tracks-title">
                  <Music size={16} />
                  {selectedAlbum}
                </h4>
                <TrackList
                  tracks={currentPlaylist}
                  playingId={playingTrackId}
                  onPlay={onPlayTrack}
                  onDelete={onDeleteTrack}
                  onAddToPlaylist={hasPlaylistFeature ? handleAddToPlaylist : undefined}
                  onRemoveFromAlbum={onRemoveFromAlbum && selectedAlbum ? (trackId) => onRemoveFromAlbum(selectedAlbum, trackId) : undefined}
                  scrollToTrackId={scrollToTrackId}
                />
              </>
            ) : (
              <div className="empty-hint">
                <Music size={32} />
                <p>选择右侧专辑查看曲目</p>
              </div>
            )}
          </div>

          {/* 右侧专辑列表 */}
          <div className="album-list-panel">
            <div className="album-list-header">
              <h4 className="album-list-title">
                <Library size={16} />
                专辑列表
              </h4>
              {!mergeTarget && !showNewAlbumInput && (
                <button
                  className="add-album-btn"
                  onClick={() => setShowNewAlbumInput(true)}
                >
                  <Plus size={14} />
                  新建
                </button>
              )}
            </div>
            
            {mergeTarget && (
              <div className="merge-mode-bar">
                <span className="merge-hint">
                  选择要合并到 <strong>{mergeTarget}</strong> 的专辑
                </span>
                <div className="merge-actions">
                  <button className="btn btn-sm btn-secondary" onClick={handleCancelMerge}>
                    取消
                  </button>
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={handleConfirmMerge}
                    disabled={mergeSelected.size === 0}
                  >
                    合并 {mergeSelected.size > 0 ? `(${mergeSelected.size})` : ''}
                  </button>
                </div>
              </div>
            )}
            
            {showNewAlbumInput && !mergeTarget && (
              <div className="new-album-input">
                <input
                  type="text"
                  placeholder="输入新专辑名称..."
                  value={newAlbumName}
                  onChange={(e) => setNewAlbumName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCreateAlbum()
                    if (e.key === 'Escape') {
                      setShowNewAlbumInput(false)
                      setNewAlbumName('')
                    }
                  }}
                  autoFocus
                />
                <button className="icon-btn confirm" onClick={handleCreateAlbum} title="确认">
                  <Check size={14} />
                </button>
                <button className="icon-btn cancel" onClick={() => { setShowNewAlbumInput(false); setNewAlbumName('') }} title="取消">
                  <X size={14} />
                </button>
              </div>
            )}
            
            <div className="album-grid">
              {albumGroups.map((group) => (
                <div
                  key={group.name}
                  className={`album-card ${selectedAlbum === group.name ? 'active' : ''} ${mergeTarget && mergeTarget !== group.name ? 'merge-selectable' : ''} ${mergeSelected.has(group.name) ? 'merge-selected' : ''}`}
                  onClick={() => {
                    if (mergeTarget && mergeTarget !== group.name) {
                      toggleMergeSelect(group.name)
                    } else if (!mergeTarget) {
                      onSelectAlbum(group.name)
                    }
                  }}
                >
                  {group.cover ? (
                    <img src={group.cover} alt={group.name} className="album-card-cover" />
                  ) : (
                    <div className="album-card-placeholder">
                      <Music size={24} />
                    </div>
                  )}
                  {editingAlbum === group.name ? (
                    <div className="album-card-edit">
                      <input
                        type="text"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleRenameAlbum(group.name)
                          if (e.key === 'Escape') setEditingAlbum(null)
                        }}
                        onClick={(e) => e.stopPropagation()}
                        autoFocus
                      />
                      <button className="icon-btn" onClick={(e) => { e.stopPropagation(); handleRenameAlbum(group.name) }}>
                        <Check size={12} />
                      </button>
                      <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setEditingAlbum(null) }}>
                        <X size={12} />
                      </button>
                    </div>
                  ) : (
                    <div className="album-card-info">
                      <span className="album-card-name">{group.name}</span>
                      <span className="album-card-count">{group.tracks.length} 首</span>
                    </div>
                  )}
                  {!mergeTarget && !editingAlbum && (
                    <div className="album-card-actions">
                      <button
                        className="icon-btn"
                        onClick={(e) => {
                          e.stopPropagation()
                          setEditingAlbum(group.name)
                          setEditingName(group.name)
                        }}
                        title="重命名"
                      >
                        <Edit2 size={12} />
                      </button>
                      <button
                        className="icon-btn"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleStartMerge(group.name)
                        }}
                        title="合并其他专辑到此"
                      >
                        <Merge size={12} />
                      </button>
                      <button
                        className="icon-btn danger"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDeleteAlbum(group.name)
                        }}
                        title="删除"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )}
                  {mergeSelected.has(group.name) && (
                    <div className="merge-check">
                      <Check size={16} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* 普通列表模式 */
        <TrackList
          tracks={sortedTracks}
          playingId={playingTrackId}
          onPlay={onPlayTrack}
          onDelete={onDeleteTrack}
          onAddToPlaylist={hasPlaylistFeature ? handleAddToPlaylist : undefined}
          scrollToTrackId={scrollToTrackId}
        />
      )}

      {/* 播放列表选择弹窗 */}
      {hasPlaylistFeature && (
        <PlaylistPicker
          open={showPlaylistPicker}
          playlists={playlists!}
          onSelect={handleSelectPlaylist}
          onCreate={onCreatePlaylist!}
          onClose={handleClosePicker}
        />
      )}
    </div>
  )
}
