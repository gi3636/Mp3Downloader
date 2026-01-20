import { useState, useCallback } from 'react'
import type { ToastType } from '../components/Toast'

export interface ToastMsg {
  id: string
  type: ToastType
  message: string
}

export function useToast() {
  const [toasts, setToasts] = useState<ToastMsg[]>([])

  const pushToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = `${Date.now()}-${Math.random()}`
    setToasts((prev) => [...prev, { id, type, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((x) => x.id !== id))
    }, 3000)
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((x) => x.id !== id))
  }, [])

  return { toasts, pushToast, removeToast }
}
