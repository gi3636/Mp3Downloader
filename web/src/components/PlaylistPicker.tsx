import { useState } from 'react'
import { ListPlus, Plus } from 'lucide-react'
import type { Playlist } from '../api'
import './PlaylistPicker.css'

interface PlaylistPickerProps {
  open: boolean
  playlists: Playlist[]
  onSelect: (playlistId: string) => void
  onCreate: (name: string) => void
  onClose: () => void
}

export function PlaylistPicker({
  open,
  playlists,
  onSelect,
  onCreate,
  onClose,
}: PlaylistPickerProps) {
  const [newPlaylistName, setNewPlaylistName] = useState('')

  if (!open) return null

  const handleCreateAndAdd = () => {
    if (newPlaylistName.trim()) {
      onCreate(newPlaylistName.trim())
      setNewPlaylistName('')
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content playlist-picker" onClick={(e) => e.stopPropagation()}>
        <h3>添加到播放列表</h3>
        
        {playlists.length > 0 ? (
          <div className="playlist-list">
            {playlists.map((pl) => (
              <div
                key={pl.id}
                className="playlist-item"
                onClick={() => onSelect(pl.id)}
              >
                <ListPlus size={16} />
                <span className="playlist-name">{pl.name}</span>
                <span className="playlist-count">{pl.track_count} 首</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-hint">暂无播放列表</p>
        )}
        
        <div className="create-playlist-row">
          <input
            type="text"
            placeholder="新播放列表名称..."
            value={newPlaylistName}
            onChange={(e) => setNewPlaylistName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreateAndAdd()}
          />
          <button
            className="btn btn-primary btn-sm"
            onClick={handleCreateAndAdd}
            disabled={!newPlaylistName.trim()}
          >
            <Plus size={16} />
            创建
          </button>
        </div>
        
        <button
          className="btn btn-secondary btn-sm"
          onClick={onClose}
        >
          取消
        </button>
      </div>
    </div>
  )
}
