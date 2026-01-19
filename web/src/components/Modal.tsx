import type { ReactNode } from 'react'
import { X } from 'lucide-react'

interface Props {
  open: boolean
  title: string
  subtitle?: string
  large?: boolean
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  toolbar?: ReactNode
}

export function Modal({ open, title, subtitle, large, onClose, children, footer, toolbar }: Props) {
  if (!open) return null

  return (
    <div className={`modal ${open ? 'visible' : ''}`}>
      <div className="modal-backdrop" onClick={onClose} />
      <div className={`modal-content ${large ? 'modal-large' : ''}`}>
        <div className="modal-header">
          <div className="modal-header-info">
            <h3 className="modal-title">{title}</h3>
            {subtitle && <span className="modal-subtitle">{subtitle}</span>}
          </div>
          <button className="modal-close" type="button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        {toolbar && <div className="modal-toolbar">{toolbar}</div>}
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}
