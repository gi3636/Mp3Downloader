import type { ChangeEvent } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Download,
  FolderDown,
  Library,
  ListMusic,
  Loader,
  Music,
  Search,
  Settings,
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
import { SettingsModal } from './components/SettingsModal'

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
  const PLAYBACK_KEY = 'mp3dl.playback.v1'

  type PlaybackSnapshot = {
    v: 1
    tab: Tab
    trackId: string | null
    currentTime: number
    wasPlaying: boolean
    shuffle: boolean
    sortMode: SortMode
    selectedAlbum: string | null
    savedAt: number
  }

  const [tab, setTab] = useState<Tab>('download')

  // 下载相关状态
  const [urlInput, setUrlInput] = useState('')
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<string>('')
  const [jobProgress, setJobProgress] = useState<number>(0)
  const [jobMeta, setJobMeta] = useState<JobMeta | null>(null)
  const [jobDownloadUrl, setJobDownloadUrl] = useState<string | null>(null)
  const [jobDownloadItems, setJobDownloadItems] = useState<DownloadItem[]>([])
  const [startLoading, setStartLoading] = useState(false)
  const [cancelLoading, setCancelLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [jobPaused, setJobPaused] = useState(false)
  const [pauseLoading, setPauseLoading] = useState(false)

  // 音乐库状态
  const [libTracks, setLibTracks] = useState<Track[]>([])
  const [libSearch, setLibSearch] = useState('')
  const [libShuffle, setLibShuffle] = useState(false)
  const [libCurrentTrackId, setLibCurrentTrackId] = useState<string | null>(null)
  const [libIsPlaying, setLibIsPlaying] = useState(false)
  const [libSortMode, setLibSortMode] = useState<SortMode>('created_desc')
  const [selectedAlbum, setSelectedAlbum] = useState<string | null>(null)
  const libPlayerRef = useRef<HTMLAudioElement | null>(null)

  const restorePlaybackRef = useRef<PlaybackSnapshot | null>(null)
  const restoredOnceRef = useRef(false)
  const lastPersistAtRef = useRef(0)

  // 播放器进度
  const [libCurrentTime, setLibCurrentTime] = useState(0)
  const [libDuration, setLibDuration] = useState(0)
  const [libSeeking, setLibSeeking] = useState(false)
  const [libSeekTime, setLibSeekTime] = useState(0)

  // 音量控制
  const [libVolume, setLibVolume] = useState(() => {
    const saved = localStorage.getItem('mp3dl.volume')
    return saved ? parseFloat(saved) : 1
  })
  const [libMuted, setLibMuted] = useState(false)

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

  // 删除确认弹窗
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [deleteConfirmTrackId, setDeleteConfirmTrackId] = useState<string | null>(null)

  // 设置弹窗
  const [settingsOpen, setSettingsOpen] = useState(false)

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

  // 当前播放曲目
  const libCurrentTrack = useMemo(() => {
    if (!libCurrentTrackId) return null
    return libTracks.find((t) => t.id === libCurrentTrackId) || null
  }, [libTracks, libCurrentTrackId])

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

  useEffect(() => {
    try {
      const raw = localStorage.getItem(PLAYBACK_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw) as PlaybackSnapshot
      if (!parsed || parsed.v !== 1) return
      restorePlaybackRef.current = parsed
      setLibShuffle(Boolean(parsed.shuffle))
      if (parsed.sortMode) setLibSortMode(parsed.sortMode)
      setSelectedAlbum(parsed.selectedAlbum || null)
      // 恢复上次的 tab，不强制切换到 library
      if (parsed.tab) setTab(parsed.tab)
    } catch {
      restorePlaybackRef.current = null
    }
  }, [])

  useEffect(() => {
    if (restoredOnceRef.current) return
    const snapshot = restorePlaybackRef.current
    if (!snapshot?.trackId) {
      // 没有需要恢复的 trackId，标记恢复完成
      restoredOnceRef.current = true
      return
    }
    
    // 等待 libTracks 加载
    if (libTracks.length === 0) return
    
    const track = libTracks.find((t) => t.id === snapshot.trackId)
    if (!track) {
      // 曲目不存在（可能被删除了），标记恢复完成
      restoredOnceRef.current = true
      return
    }

    restoredOnceRef.current = true

    if (snapshot.sortMode === 'album') {
      setLibSortMode('album')
      setSelectedAlbum(snapshot.selectedAlbum || track.album_title || track.album || '未知专辑')
    }

    setLibCurrentTrackId(track.id)

    const el = libPlayerRef.current
    if (!el) return
    el.src = track.stream_url

    const applyTime = () => {
      try {
        const maxTime = Number.isFinite(el.duration) ? el.duration : Number.POSITIVE_INFINITY
        el.currentTime = Math.max(0, Math.min(snapshot.currentTime || 0, maxTime))
      } catch {
        // ignore
      }
    }

    if (el.readyState >= 1) {
      applyTime()
    } else {
      el.addEventListener('loadedmetadata', applyTime, { once: true })
    }

    if (snapshot.wasPlaying) {
      void el.play().catch(() => {
        // ignore
      })
    }
  }, [libTracks])

  useEffect(() => {
    // 如果还没恢复完成，不要保存（避免覆盖掉之前的状态）
    if (!restoredOnceRef.current && restorePlaybackRef.current?.trackId) return
    
    const now = Date.now()
    if (now - lastPersistAtRef.current < 1000) return
    lastPersistAtRef.current = now
    const snapshot: PlaybackSnapshot = {
      v: 1,
      tab,
      trackId: libCurrentTrackId,
      currentTime: libCurrentTime,
      wasPlaying: libIsPlaying,
      shuffle: libShuffle,
      sortMode: libSortMode,
      selectedAlbum,
      savedAt: now,
    }
    try {
      localStorage.setItem(PLAYBACK_KEY, JSON.stringify(snapshot))
    } catch {
      // ignore
    }
  }, [tab, libCurrentTrackId, libCurrentTime, libIsPlaying, libShuffle, libSortMode, selectedAlbum])

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

  const togglePlayPause = useCallback(() => {
    const el = libPlayerRef.current
    if (!el) return
    if (el.paused) {
      void el.play()
    } else {
      el.pause()
    }
  }, [])

  // 轮询任务状态
  async function pollJob(jobId: string) {
    try {
      const data = await api.getJob(jobId)
      setJobStatus(data.status)
      setJobProgress(data.progress || 0)
      setJobMeta(data.meta || null)
      setJobDownloadUrl(data.download_url || null)
      setJobDownloadItems(data.download_items || [])
      setJobPaused(data.paused || false)

      if (['done', 'error', 'canceled'].includes(data.status)) {
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
        }
        if (data.status === 'done') {
          pushToast('下载完成！', 'success')
          refreshLibrary()
        } else if (data.status === 'error') {
          pushToast(data.message || '下载失败', 'error')
        }
      }
    } catch (e: any) {
      if (e?.status === 404) {
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
        }
        setCurrentJobId(null)
        setJobStatus('')
        setJobProgress(0)
        setJobMeta(null)
        setJobDownloadUrl(null)
        setJobDownloadItems([])
        setJobPaused(false)
        pushToast('任务不存在或已被清理，已停止轮询', 'info')
        return
      }
      pushToast(e?.message || '获取状态失败', 'error')
    }
  }

  function startPolling(jobId: string) {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
    }
    pollJob(jobId)
    pollTimerRef.current = window.setInterval(() => pollJob(jobId), 1000)
  }

  // 开始下载
  async function handleStart() {
    const url = urlInput.trim()
    if (!url) {
      pushToast('请输入 YouTube 链接', 'error')
      return
    }

    console.log('handleStart called with url:', url)
    setStartLoading(true)
    try {
      // 先解析链接
      console.log('Resolving URL...')
      const resolveData = await api.resolveUrl(url)
      console.log('Resolve result:', resolveData)

      if (resolveData.mode === 'choose') {
        // 需要选择专辑
        const choice = await openChoiceModal(resolveData.choices || [])
        if (!choice) {
          setStartLoading(false)
          return
        }
        // 重新解析选择的链接
        const newResolve = await api.resolveUrl(choice)
        if (newResolve.mode === 'playlist') {
          const selection = await openTrackSelectModal(newResolve.playlist!)
          if (!selection) {
            setStartLoading(false)
            return
          }
          const startData = await api.createJob({
            url: choice,
            video_urls: selection.urls,
            video_titles: selection.titles,
            video_thumbnails: selection.thumbnails,
          })
          setCurrentJobId(startData.job_id)
          startPolling(startData.job_id)
        } else {
          const startData = await api.createJob({ url: choice })
          setCurrentJobId(startData.job_id)
          startPolling(startData.job_id)
        }
      } else if (resolveData.mode === 'playlist') {
        // 播放列表，选择曲目
        const selection = await openTrackSelectModal(resolveData.playlist!)
        if (!selection) {
          setStartLoading(false)
          return
        }
        const startData = await api.createJob({
          url,
          video_urls: selection.urls,
          video_titles: selection.titles,
          video_thumbnails: selection.thumbnails,
        })
        setCurrentJobId(startData.job_id)
        startPolling(startData.job_id)
      } else {
        // 单曲
        console.log('Direct mode, creating job...')
        const startData = await api.createJob({ url })
        console.log('Job created:', startData)
        setCurrentJobId(startData.job_id)
        startPolling(startData.job_id)
      }
    } catch (e: any) {
      console.error('handleStart error:', e)
      pushToast(e?.message || '开始下载失败', 'error')
    } finally {
      setStartLoading(false)
    }
  }

  // 取消下载
  async function handleCancel() {
    if (!currentJobId) return
    setCancelLoading(true)
    try {
      await api.cancelJob(currentJobId)
      pushToast('已取消下载', 'info')
    } catch (e: any) {
      pushToast(e?.message || '取消失败', 'error')
    } finally {
      setCancelLoading(false)
    }
  }

  // 删除任务
  async function handleDelete() {
    if (!currentJobId) return
    setDeleteLoading(true)
    try {
      await api.deleteJob(currentJobId)
      setCurrentJobId(null)
      setJobStatus('')
      setJobProgress(0)
      setJobMeta(null)
      setJobDownloadUrl(null)
      setJobDownloadItems([])
      pushToast('已删除任务', 'info')
    } catch (e: any) {
      pushToast(e?.message || '删除失败', 'error')
    } finally {
      setDeleteLoading(false)
    }
  }

  // 暂停/继续
  async function handlePauseResume() {
    if (!currentJobId) return
    setPauseLoading(true)
    try {
      if (jobPaused) {
        await api.resumeJob(currentJobId)
      } else {
        await api.pauseJob(currentJobId)
      }
    } catch (e: any) {
      pushToast(e?.message || '操作失败', 'error')
    } finally {
      setPauseLoading(false)
    }
  }

  // 暂停/继续单个下载项
  async function handlePauseItem(index: number, isPaused: boolean) {
    if (!currentJobId) return
    try {
      if (isPaused) {
        await api.resumeJobItem(currentJobId, index)
      } else {
        await api.pauseJobItem(currentJobId, index)
      }
    } catch (e: any) {
      pushToast(e?.message || '操作失败', 'error')
    }
  }

  // 删除音乐库曲目
  async function handleDeleteLibTrack(trackId: string) {
    try {
      await api.deleteLibraryTrack(trackId)
      pushToast('已删除', 'success')
      refreshLibrary()
    } catch (e: any) {
      pushToast(e?.message || '删除失败', 'error')
    }
  }

  // 删除当前播放的曲目（带确认）
  function handleDeleteCurrentTrack() {
    if (!libCurrentTrackId) return
    setDeleteConfirmTrackId(libCurrentTrackId)
    setDeleteConfirmOpen(true)
  }

  async function confirmDeleteCurrentTrack() {
    if (!deleteConfirmTrackId) return
    
    // 先切换到下一首
    const currentId = deleteConfirmTrackId
    nextTrack()
    
    // 如果只有一首歌，停止播放
    if (currentPlaylist.length <= 1) {
      const el = libPlayerRef.current
      if (el) {
        el.pause()
        el.src = ''
      }
      setLibCurrentTrackId(null)
    }
    
    // 关闭弹窗
    setDeleteConfirmOpen(false)
    setDeleteConfirmTrackId(null)
    
    // 删除曲目
    try {
      await api.deleteLibraryTrack(currentId)
      pushToast('已删除', 'success')
      refreshLibrary()
    } catch (e: any) {
      pushToast(e?.message || '删除失败', 'error')
    }
  }

  function cancelDeleteCurrentTrack() {
    setDeleteConfirmOpen(false)
    setDeleteConfirmTrackId(null)
  }

  // 初始化
  useEffect(() => {
    refreshLibrary()
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
      }
    }
  }, [])

  // 空格键暂停/播放
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 如果焦点在输入框、文本区域或按钮上，不处理空格键
      const target = e.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'BUTTON' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable
      ) {
        return
      }

      if (e.code === 'Space' && libCurrentTrackId) {
        e.preventDefault()
        togglePlayPause()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [libCurrentTrackId, togglePlayPause])

  // 音频事件监听
  useEffect(() => {
    const el = libPlayerRef.current
    if (!el) return

    const onPlay = () => setLibIsPlaying(true)
    const onPause = () => setLibIsPlaying(false)
    const onEnded = () => nextTrack()
    const onTimeUpdate = () => {
      if (!libSeeking) {
        setLibCurrentTime(el.currentTime)
      }
    }
    const onDurationChange = () => setLibDuration(el.duration || 0)
    const onLoadedMetadata = () => setLibDuration(el.duration || 0)

    el.addEventListener('play', onPlay)
    el.addEventListener('pause', onPause)
    el.addEventListener('ended', onEnded)
    el.addEventListener('timeupdate', onTimeUpdate)
    el.addEventListener('durationchange', onDurationChange)
    el.addEventListener('loadedmetadata', onLoadedMetadata)

    return () => {
      el.removeEventListener('play', onPlay)
      el.removeEventListener('pause', onPause)
      el.removeEventListener('ended', onEnded)
      el.removeEventListener('timeupdate', onTimeUpdate)
      el.removeEventListener('durationchange', onDurationChange)
      el.removeEventListener('loadedmetadata', onLoadedMetadata)
    }
  }, [libSeeking, libCurrentIndex, currentPlaylist.length, libShuffle])

  // Seek 处理
  function handleSeekChange(time: number) {
    setLibSeeking(true)
    setLibSeekTime(time)
  }

  function handleSeekCommit(time: number) {
    const el = libPlayerRef.current
    if (el) {
      el.currentTime = time
    }
    setLibSeeking(false)
  }

  // 音量处理
  function handleVolumeChange(volume: number) {
    setLibVolume(volume)
    setLibMuted(false)
    localStorage.setItem('mp3dl.volume', String(volume))
    const el = libPlayerRef.current
    if (el) {
      el.volume = volume
      el.muted = false
    }
  }

  // 同步音量到播放器
  useEffect(() => {
    const el = libPlayerRef.current
    if (el) {
      el.volume = libMuted ? 0 : libVolume
      el.muted = libMuted
    }
  }, [libVolume, libMuted])

  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 忽略输入框内的按键
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
      
      // 只在有曲目播放时响应
      if (!libCurrentTrackId) return

      switch (e.code) {
        case 'Space':
          e.preventDefault()
          togglePlayPause()
          break
        case 'ArrowLeft':
          e.preventDefault()
          prevTrack()
          break
        case 'ArrowRight':
          e.preventDefault()
          nextTrack()
          break
        case 'ArrowUp':
          e.preventDefault()
          handleVolumeChange(Math.min(1, libVolume + 0.1))
          break
        case 'ArrowDown':
          e.preventDefault()
          handleVolumeChange(Math.max(0, libVolume - 0.1))
          break
        case 'KeyM':
          e.preventDefault()
          setLibMuted(!libMuted)
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [libCurrentTrackId, libVolume, libMuted])

  return (
    <div className="app">
      {/* Toast 通知 */}
      <div className="toast-container">
        {toasts.map((t) => (
          <Toast key={t.id} type={t.type} message={t.message} />
        ))}
      </div>

      {/* 选择专辑弹窗 */}
      <ChoiceModal
        open={choiceModalOpen}
        choices={choiceOptions}
        onSelect={(url) => closeChoiceModal(url)}
        onClose={() => closeChoiceModal(null)}
      />

      {/* 选择曲目弹窗 */}
      <TrackSelectModal
        open={trackSelectOpen}
        playlist={trackSelectPlaylist}
        onConfirm={(sel) => closeTrackSelectModal(sel)}
        onClose={() => closeTrackSelectModal(null)}
      />

      {/* 删除确认弹窗 */}
      {deleteConfirmOpen && (
        <div className="modal visible">
          <div className="modal-backdrop" onClick={cancelDeleteCurrentTrack} />
          <div className="modal-content" style={{ maxWidth: '400px' }}>
            <div className="modal-header">
              <h3 className="modal-title">确认删除</h3>
            </div>
            <div className="modal-body">
              <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                确定要删除当前播放的歌曲吗？此操作不可撤销。
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" type="button" onClick={cancelDeleteCurrentTrack}>
                取消
              </button>
              <button className="btn btn-danger" type="button" onClick={confirmDeleteCurrentTrack}>
                <Trash2 size={16} />
                删除
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 隐藏的音频播放器 */}
      <audio ref={libPlayerRef} />

      {/* 设置弹窗 */}
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onToast={pushToast}
      />

      {/* 页面标题 */}
      <header className="app-header">
        <div className="header-content">
          <h1>🎵 YouTube 音乐下载器</h1>
          <p>下载 YouTube 视频/播放列表，转换为高品质 MP3</p>
        </div>
        <button
          className="settings-btn"
          onClick={() => setSettingsOpen(true)}
          title="设置"
        >
          <Settings size={20} />
        </button>
      </header>

      {/* 标签页 */}
      <div className="tabs">
        <button
          className={`tab ${tab === 'download' ? 'active' : ''}`}
          onClick={() => setTab('download')}
        >
          <Download size={16} />
          下载
        </button>
        <button
          className={`tab ${tab === 'library' ? 'active' : ''}`}
          onClick={() => setTab('library')}
        >
          <Library size={16} />
          音乐库
          {libBadgeCount > 0 && <span className="badge">{libBadgeCount}</span>}
        </button>
      </div>

      {/* 下载页面 */}
      {tab === 'download' && (
        <div className="download-page">
          <div className="input-row">
            <input
              type="text"
              className="url-input"
              placeholder="输入 YouTube 链接..."
              value={urlInput}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setUrlInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleStart()}
            />
            <button
              className="btn btn-primary"
              onClick={handleStart}
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
                  onClick={handleCancel}
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
                  onClick={handleDelete}
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
                onPauseAll={handlePauseResume}
                onPauseItem={handlePauseItem}
              />
            </div>
          )}
        </div>
      )}

      {/* 音乐库页面 */}
      {tab === 'library' && (
        <div className="library-page">
          {/* 工具栏 */}
          <div className="library-toolbar">
            <div className="search-box">
              <Search size={16} />
              <input
                type="text"
                placeholder="搜索..."
                value={libSearch}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setLibSearch(e.target.value)}
              />
            </div>
            <select
              className="sort-select"
              value={libSortMode}
              onChange={(e: ChangeEvent<HTMLSelectElement>) =>
                setLibSortMode(e.target.value as SortMode)
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
          {libSortMode === 'album' ? (
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
                      playingId={libCurrentTrackId}
                      onPlay={playTrack}
                      onDelete={handleDeleteLibTrack}
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
                      onClick={() => setSelectedAlbum(group.name)}
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
              tracks={sortedLibTracks}
              playingId={libCurrentTrackId}
              onPlay={playTrack}
              onDelete={handleDeleteLibTrack}
            />
          )}

        </div>
      )}

      {/* 悬浮播放器 - 始终显示在底部 */}
      <div className="floating-player">
        {libCurrentTrack ? (
          <NowPlaying
            track={libCurrentTrack}
            currentIndex={libCurrentIndex}
            totalCount={currentPlaylist.length}
            onClickTitle={() => setTab('library')}
            onDelete={handleDeleteCurrentTrack}
          />
        ) : (
          <div className="now-playing empty">
            <Music size={24} />
            <span>选择一首歌曲开始播放</span>
          </div>
        )}
        <PlayerControls
          isPlaying={libIsPlaying}
          shuffle={libShuffle}
          currentTime={libCurrentTime}
          duration={libDuration}
          seeking={libSeeking}
          seekTime={libSeekTime}
          volume={libVolume}
          muted={libMuted}
          onPlayPause={togglePlayPause}
          onPrev={prevTrack}
          onNext={nextTrack}
          onToggleShuffle={() => setLibShuffle(!libShuffle)}
          onSeekChange={handleSeekChange}
          onSeekCommit={handleSeekCommit}
          onVolumeChange={handleVolumeChange}
          onToggleMute={() => setLibMuted(!libMuted)}
        />
      </div>
    </div>
  )
}
