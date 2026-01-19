import type { ChangeEvent } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Download,
  FolderDown,
  Library,
  ListMusic,
  Loader,
  Music,
  Search,
  Trash2,
  X,
} from 'lucide-react'
import type { DownloadItem, JobMeta, PlaylistInfo, ResolveChoice, Track } from './types'
import * as api from './api'
import { statusText } from './utils'
import { Toast, type ToastType } from './components/Toast'
import { ChoiceModal } from './components/ChoiceModal'
import { TrackSelectModal, type TrackSelection } from './components/TrackSelectModal'
import { DownloadItemsList } from './components/DownloadItemsList'
import { TrackList } from './components/TrackList'
import { NowPlaying } from './components/NowPlaying'
import { PlayerControls } from './components/PlayerControls'

type Tab = 'download' | 'library'
type SortMode = 'created_desc' | 'created_asc' | 'alpha_asc' | 'alpha_desc' | 'album'

interface ToastMsg {
  id: string
  type: ToastType
  message: string
}

interface AlbumGroup {
  name: string
  cover: string | null
  tracks: Track[]
}

export default function App() {
  const [tab, setTab] = useState<Tab>('download')

  // 下载相关状态
  const [urlInput, setUrlInput] = useState('')
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<string>('')
  const [jobProgress, setJobProgress] = useState<number>(0)
  const [jobMeta, setJobMeta] = useState<JobMeta | null>(null)
  const [jobDownloadUrl, setJobDownloadUrl] = useState<string | null>(null)
  const [jobTracks, setJobTracks] = useState<Track[]>([])
  const [jobDownloadItems, setJobDownloadItems] = useState<DownloadItem[]>([])
  const [startLoading, setStartLoading] = useState(false)
  const [cancelLoading, setCancelLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [jobPaused, setJobPaused] = useState(false)
  const [pauseLoading, setPauseLoading] = useState(false)

  // 下载播放器
  const jobPlayerRef = useRef<HTMLAudioElement | null>(null)
  const [jobPlayingId, setJobPlayingId] = useState<string | null>(null)

  // 音乐库状态
  const [libTracks, setLibTracks] = useState<Track[]>([])
  const [libSearch, setLibSearch] = useState('')
  const [libShuffle, setLibShuffle] = useState(false)
  const [libCurrentTrackId, setLibCurrentTrackId] = useState<string | null>(null)
  const [libIsPlaying, setLibIsPlaying] = useState(false)
  const [libSortMode, setLibSortMode] = useState<SortMode>('created_desc')
  const [selectedAlbum, setSelectedAlbum] = useState<string | null>(null)
  const libPlayerRef = useRef<HTMLAudioElement | null>(null)

  // 播放器进度
  const [libCurrentTime, setLibCurrentTime] = useState(0)
  const [libDuration, setLibDuration] = useState(0)
  const [libSeeking, setLibSeeking] = useState(false)
  const [libSeekTime, setLibSeekTime] = useState(0)

  // Toast 通知
  const [toasts, setToasts] = useState<ToastMsg[]>([])

  // 轮询定时器
  const pollTimerRef = useRef<number | null>(null)

  // 选择专辑弹窗
  const [choiceModalOpen, setChoiceModalOpen] = useState(false)
  const [choiceOptions, setChoiceOptions] = useState<ResolveChoice[]>([])
  const choiceResolveRef = useRef<((v: string | null) => void) | null>(null)

  // 选择曲目弹窗
  const [trackSelectOpen, setTrackSelectOpen] = useState(false)
  const [trackSelectPlaylist, setTrackSelectPlaylist] = useState<PlaylistInfo | null>(null)
  const trackSelectResolveRef = useRef<((v: TrackSelection | null) => void) | null>(null)

  // 计算属性
  const libBadgeCount = libTracks.length
  const isRunning = ['running', 'queued', 'canceling'].includes(jobStatus)
  const albumHasAny = Boolean(jobMeta?.title || jobMeta?.thumbnail_url || jobMeta?.total_items)

  // 排序后的曲目
  const sortedLibTracks = useMemo(() => {
    let tracks = [...libTracks]
    const q = libSearch.trim().toLowerCase()
    if (q) {
      tracks = tracks.filter((t) => (t.title || '').toLowerCase().includes(q))
    }
    
    switch (libSortMode) {
      case 'created_desc':
        tracks.sort((a, b) => (b.created_at || 0) - (a.created_at || 0))
        break
      case 'created_asc':
        tracks.sort((a, b) => (a.created_at || 0) - (b.created_at || 0))
        break
      case 'alpha_asc':
        tracks.sort((a, b) => (a.title || '').localeCompare(b.title || ''))
        break
      case 'alpha_desc':
        tracks.sort((a, b) => (b.title || '').localeCompare(a.title || ''))
        break
      case 'album':
        tracks.sort((a, b) => {
          const albumA = a.album_title || a.album || ''
          const albumB = b.album_title || b.album || ''
          if (albumA !== albumB) return albumA.localeCompare(albumB)
          return (a.title || '').localeCompare(b.title || '')
        })
        break
    }
    return tracks
  }, [libTracks, libSearch, libSortMode])

  // 按专辑分组
  const albumGroups = useMemo((): AlbumGroup[] => {
    if (libSortMode !== 'album') return []
    
    const groups: Map<string, AlbumGroup> = new Map()
    for (const track of sortedLibTracks) {
      const albumName = track.album_title || track.album || '未知专辑'
      if (!groups.has(albumName)) {
        groups.set(albumName, {
          name: albumName,
          cover: track.cover_url || null,
          tracks: [],
        })
      }
      groups.get(albumName)!.tracks.push(track)
    }
    return Array.from(groups.values())
  }, [sortedLibTracks, libSortMode])

  // 当前播放列表（专辑模式下只播放选中专辑）
  const currentPlaylist = useMemo(() => {
    if (libSortMode === 'album' && selectedAlbum) {
      const group = albumGroups.find((g) => g.name === selectedAlbum)
      return group?.tracks || []
    }
    return sortedLibTracks
  }, [libSortMode, selectedAlbum, albumGroups, sortedLibTracks])

  // 当前播放索引
  const libCurrentIndex = useMemo(() => {
    if (!libCurrentTrackId) return -1
    return currentPlaylist.findIndex((t) => t.id === libCurrentTrackId)
  }, [currentPlaylist, libCurrentTrackId])

  // Toast 通知
  function pushToast(message: string, type: ToastType = 'info') {
    const id = `${Date.now()}-${Math.random()}`
    setToasts((prev) => [...prev, { id, type, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((x) => x.id !== id))
    }, 3000)
  }

  // 选择专辑弹窗
  function openChoiceModal(choices: ResolveChoice[]) {
    setChoiceOptions(choices)
    setChoiceModalOpen(true)
    return new Promise<string | null>((resolve) => {
      choiceResolveRef.current = resolve
    })
  }

  function closeChoiceModal(result: string | null) {
    setChoiceModalOpen(false)
    choiceResolveRef.current?.(result)
    choiceResolveRef.current = null
  }

  // 选择曲目弹窗
  function openTrackSelectModal(playlist: PlaylistInfo) {
    setTrackSelectPlaylist(playlist)
    setTrackSelectOpen(true)
    return new Promise<TrackSelection | null>((resolve) => {
      trackSelectResolveRef.current = resolve
    })
  }

  function closeTrackSelectModal(result: TrackSelection | null) {
    setTrackSelectOpen(false)
    trackSelectResolveRef.current?.(result)
    trackSelectResolveRef.current = null
  }

  // 音乐库操作
  async function refreshLibrary() {
    try {
      const data = await api.getLibraryTracks()
      setLibTracks(data.tracks || [])
    } catch (e: any) {
      pushToast(e?.message || '加载音乐库失败', 'error')
    }
  }

  function playTrack(track: Track) {
    const el = libPlayerRef.current
    if (!el) return
    
    // 如果是专辑模式，设置当前专辑
    if (libSortMode === 'album') {
      const albumName = track.album_title || track.album || '未知专辑'
      setSelectedAlbum(albumName)
    }
    
    setLibCurrentTrackId(track.id)
    el.src = track.stream_url
    void el.play()
  }

  function playAtIndex(index: number) {
    if (index < 0 || index >= currentPlaylist.length) return
    playTrack(currentPlaylist[index])
  }

  function nextTrack() {
    if (!currentPlaylist.length) return
    if (libShuffle) {
      if (currentPlaylist.length === 1) {
        playAtIndex(0)
        return
      }
      let next = libCurrentIndex
      while (next === libCurrentIndex) {
        next = Math.floor(Math.random() * currentPlaylist.length)
      }
      playAtIndex(next)
      return
    }
    const next = (libCurrentIndex < 0 ? 0 : libCurrentIndex + 1) % currentPlaylist.length
    playAtIndex(next)
  }

  function prevTrack() {
    if (!currentPlaylist.length) return
    if (libShuffle) {
      nextTrack()
      return
    }
    const prev = (libCurrentIndex < 0 ? 0 : libCurrentIndex - 1 + currentPlaylist.length) % currentPlaylist.length
    playAtIndex(prev)
  }
