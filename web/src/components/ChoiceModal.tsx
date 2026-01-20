import { X } from 'lucide-react'
import type { ResolveChoice } from '../types'
import './ChoiceModal.css'

interface Props {
  open: boolean
  choices: ResolveChoice[]
  onClose: () => void
  onSelect: (url: string) => void
}

export function ChoiceModal({ open, choices, onClose, onSelect }: Props) {
  if (!open) return null

  return (
    <div className={`modal ${open ? 'visible' : ''}`}>
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal-content">
        <div className="modal-header">
          <h3 className="modal-title">选择要下载的专辑</h3>
          <button className="modal-close" type="button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div className="modal-body">
          <div className="choice-list">
            {choices.map((c) => (
              <div key={c.url} className="choice-item" onClick={() => onSelect(c.url)}>
                <div className="choice-title">{c.title || c.url}</div>
                <div className="choice-url">{c.url}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" type="button" onClick={onClose}>
            取消
          </button>
        </div>
      </div>
    </div>
  )
}
