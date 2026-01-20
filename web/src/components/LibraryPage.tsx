import type { ChangeEvent } from 'react'
import { FolderOpen, Library, Music, Search } from 'lucide-react'
import type { Track } from '../types'
import * as api from '../api'
import { TrackList } from './TrackList'

export type SortMode = 'created_desc' | 'created_asc' | 'alpha_asc' | 'alpha_desc' | 'album'

export interface AlbumGroup {
  name: string
  cover: string | null
  tracks: Track[]
}

interface LibraryPageProps {
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
}

export function LibraryPage({
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
}: LibraryPageProps) {
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
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => api.openDownloadFolder()}
          title="打开文件位置"
        >
          <FolderOpen size={16} />
        </button>
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
            <h4 className="album-list-title">
              <Library size={16} />
              专辑列表
            </h4>
            <div className="album-grid">
              {albumGroups.map((group) => (
                <div
                  key={group.name}
                  className={`album-card ${selectedAlbum === group.name ? 'active' : ''}`}
                  onClick={() => onSelectAlbum(group.name)}
                >
                  {group.cover ? (
                    <img src={group.cover} alt={group.name} className="album-card-cover" />
                  ) : (
                    <div className="album-card-placeholder">
                      <Music size={24} />
                    </div>
                  )}
                  <div className="album-card-info">
                    <span className="album-card-name">{group.name}</span>
                    <span className="album-card-count">{group.tracks.length} 首</span>
                  </div>
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
        />
      )}
    </div>
  )
}
