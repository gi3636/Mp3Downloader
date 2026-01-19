import { useState } from 'react'
import { Check, CheckSquare, Download, Square } from 'lucide-react'
import type { PlaylistInfo } from '../types'
import { Modal } from './Modal'
import { formatDuration } from '../utils'

export interface TrackSelection {
  urls: string[]
  titles: string[]
  thumbnails: string[]
}

interface Props {
  open: boolean
  playlist: PlaylistInfo | null
  onClose: () => void
  onConfirm: (selection: TrackSelection) => void
}

export function TrackSelectModal({ open, playlist, onClose, onConfirm }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const entries = playlist?.entries || []
  const defaultThumb = playlist?.thumbnail || ''

  const toggle = (url: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(url)) next.delete(url)
      else next.add(url)
      return next
    })
  }

  const selectAll = () => {
    setSelected(new Set(entries.map((e) => e.url).filter(Boolean)))
  }

  const selectNone = () => setSelected(new Set())

  const handleConfirm = () => {
    const urls = Array.from(selected)
    const titles = urls.map((u) => entries.find((e) => e.url === u)?.title || '')
    const thumbnails = urls.map((u) => entries.find((e) => e.url === u)?.thumbnail || defaultThumb)
    onConfirm({ urls, titles, thumbnails })
    setSelected(new Set())
  }

  const handleClose = () => {
    setSelected(new Set())
    onClose()
  }

  return (
    <Modal
      open={open}
      title={playlist?.title || '选择要下载的曲目'}
      subtitle={`已选择 ${selected.size} 首`}
      large
      onClose={handleClose}
      toolbar={
        <>
          <button className="btn btn-secondary btn-sm" type="button" onClick={selectAll}>
            <CheckSquare size={16} />
            <span>全选</span>
          </button>
          <button className="btn btn-secondary btn-sm" type="button" onClick={selectNone}>
            <Square size={16} />
            <span>取消全选</span>
          </button>
          <div className="toolbar-spacer" />
          <span className="toolbar-info">共 {entries.length} 首</span>
        </>
      }
      footer={
        <>
          <button className="btn btn-secondary" type="button" onClick={handleClose}>
            取消
          </button>
          <button
            className="btn btn-primary"
            type="button"
            disabled={selected.size === 0}
            onClick={handleConfirm}
          >
            <Download size={16} />
            <span>下载选中</span>
          </button>
        </>
      }
    >
      <div className="track-select-list">
        {entries.map((e) => {
          const isSelected = selected.has(e.url)
          const cover = e.thumbnail || defaultThumb
          return (
            <div
              key={`${e.index}-${e.url}`}
              className={`track-select-item ${isSelected ? 'selected' : ''}`}
              onClick={() => toggle(e.url)}
            >
              <div className="track-select-checkbox">{isSelected && <Check size={14} />}</div>
              <img
                className="track-select-cover"
                alt=""
                src={cover}
                onError={(ev) => ((ev.target as HTMLImageElement).style.display = 'none')}
              />
              <span className="track-select-index">{e.index}</span>
              <div className="track-select-info">
                <div className="track-select-title">{e.title}</div>
              </div>
              <span className="track-select-duration">{formatDuration(e.duration)}</span>
            </div>
          )
        })}
      </div>
    </Modal>
  )
}
