import { Trash2 } from 'lucide-react'

interface ConfirmModalProps {
  open: boolean
  title: string
  message: string
  confirmText?: string
  confirmIcon?: React.ReactNode
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmModal({
  open,
  title,
  message,
  confirmText = '确认',
  confirmIcon,
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  if (!open) return null

  return (
    <div className="modal visible">
      <div className="modal-backdrop" onClick={onCancel} />
      <div className="modal-content" style={{ maxWidth: '400px' }}>
        <div className="modal-header">
          <h3 className="modal-title">{title}</h3>
        </div>
        <div className="modal-body">
          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>{message}</p>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" type="button" onClick={onCancel}>
            取消
          </button>
          <button
            className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
            type="button"
            onClick={onConfirm}
          >
            {confirmIcon || (danger && <Trash2 size={16} />)}
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
