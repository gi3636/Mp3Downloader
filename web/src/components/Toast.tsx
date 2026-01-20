import { AlertCircle, CheckCircle, Info } from 'lucide-react'
import './Toast.css'

export type ToastType = 'success' | 'error' | 'info'

interface Props {
  type: ToastType
  message: string
}

export function Toast({ type, message }: Props) {
  const Icon = type === 'success' ? CheckCircle : type === 'error' ? AlertCircle : Info

  return (
    <div className={`toast ${type}`}>
      <Icon className="toast-icon" />
      <span className="toast-message">{message}</span>
    </div>
  )
}
