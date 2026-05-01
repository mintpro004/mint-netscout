import { useState, useEffect, useCallback, useRef } from 'react'

// Stable event-emitter — no mutable module-level refs
const listeners = new Set()
let _id = 0

export function toast(msg, type = 'info', duration = 3200) {
  const id = ++_id
  listeners.forEach(fn => fn({ id, msg, type, duration }))
}
toast.success = (msg, dur) => toast(msg, 'success', dur)
toast.error   = (msg, dur) => toast(msg, 'error',   dur)
toast.info    = (msg, dur) => toast(msg, 'info',    dur)

export function useToasts() {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())

  useEffect(() => {
    const activeTimers = timers.current
    const handler = ({ id, msg, type, duration }) => {
      setToasts(p => [...p, { id, msg, type }])
      const t = setTimeout(() => {
        setToasts(p => p.filter(x => x.id !== id))
        activeTimers.delete(id)
      }, duration)
      activeTimers.set(id, t)
    }
    listeners.add(handler)
    return () => {
      listeners.delete(handler)
      activeTimers.forEach(clearTimeout)
    }
  }, [])

  const dismiss = useCallback((id) => {
    setToasts(p => p.filter(x => x.id !== id))
    clearTimeout(timers.current.get(id))
    timers.current.delete(id)
  }, [])

  return { toasts, dismiss }
}
