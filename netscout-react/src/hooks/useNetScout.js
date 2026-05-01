import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { api, createSocket } from '../api'

export function useNetScout() {
  const [devices,    setDevices]   = useState([])
  const [unsafe,     setUnsafe]    = useState([])
  const [status,     setStatus]    = useState(null)
  const [alerts,     setAlerts]    = useState([])
  const [scanning,   setScanning]  = useState(false)
  const [scanMsg,    setScanMsg]   = useState('')
  const [connected,  setConnected] = useState(false)
  const [hiddenMacs, setHiddenMacs] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem('ns_hidden') || '[]')) }
    catch { return new Set() }
  })

  const sockRef = useRef(null)
  const pollRef = useRef(null)

  // ── Independent fetches — one failure never wipes other data ─────────────
  const fetchAll = useCallback(async () => {
    api.getDevices().then(d => setDevices(d.devices || [])).catch(e => console.warn('devices:', e))
    api.getUnsafe().then(u => setUnsafe(u.unsafe_zone || [])).catch(e => console.warn('unsafe:', e))
    api.getStatus().then(setStatus).catch(e => console.warn('status:', e))
  }, [])

  // ── Socket ────────────────────────────────────────────────────────────────
  useEffect(() => {
    const sock = createSocket()
    sockRef.current = sock

    sock.on('connect',       () => { setConnected(true); fetchAll() })
    sock.on('disconnect',    () => setConnected(false))
    sock.on('scan_progress', d  => { setScanning(true); setScanMsg(d.message || 'Scanning…') })
    sock.on('scan_complete', () => { setScanning(false); setScanMsg(''); fetchAll() }) // always re-fetch — don't trust partial payload
    sock.on('scan_error',    () => { setScanning(false); setScanMsg('') })
    sock.on('alert',         a  => setAlerts(p => [{ ...a, _id: Date.now() + Math.random() }, ...p].slice(0, 200)))

    fetchAll()
    pollRef.current = setInterval(fetchAll, 20_000)

    return () => { sock.disconnect(); clearInterval(pollRef.current) }
  }, [fetchAll])

  // ── Actions — all wrapped with try/catch so errors surface as return values
  const triggerScan = useCallback(async (aggressive = false) => {
    setScanning(true)
    setScanMsg(aggressive ? 'Initiating AGGRESSIVE deep discovery…' : 'Initiating standard discovery…')
    try {
      await api.triggerScan(aggressive)
    } catch (e) {
      setScanning(false)
      setScanMsg('')
      return { success: false, error: e.message }
    }
    return { success: true }
  }, [])

  const trustDevice = useCallback(async (mac, trusted) => {
    try {
      const res = await api.trustDevice(mac, trusted)
      if (res.success) setDevices(p => p.map(d => d.mac === mac ? { ...d, is_trusted: trusted } : d))
      return res
    } catch (e) {
      return { success: false, error: e.message }
    }
  }, [])

  const blockDevice = useCallback(async (mac, blocked) => {
    try {
      const res = await api.blockDevice(mac, blocked)
      if (res.success) setDevices(p => p.map(d => d.mac === mac ? { ...d, is_trusted: !blocked } : d))
      return res
    } catch (e) {
      return { success: false, error: e.message }
    }
  }, [])

  const removeDevice = useCallback(async (mac) => {
    try {
      const res = await api.removeDevice(mac)
      if (res.success) setDevices(p => p.filter(d => d.mac !== mac))
      return res
    } catch (e) {
      return { success: false, error: e.message }
    }
  }, [])

  const investigateDevice = useCallback(async (mac) => {
    setScanning(true)
    setScanMsg('Running deep port investigation…')
    try {
      const res = await api.investigateDevice(mac)
      setScanning(false)
      setScanMsg('')
      if (res.success) {
        setDevices(p => p.map(d => d.mac === mac ? { ...d, open_ports: res.ports || [] } : d))
      }
      return res
    } catch (e) {
      setScanning(false)
      setScanMsg('')
      return { success: false, error: e.message }
    }
  }, [])

  // FIX: use _id (injected above) for stable identity so ACK works even when
  // server returns alerts without alert_type
  const ackAlert = useCallback((a) => {
    setAlerts(p => p.map(x => x._id === a._id ? { ...x, acked: true } : x))
  }, [])

  const ackAll = useCallback(() => {
    setAlerts(p => p.map(x => ({ ...x, acked: true })))
  }, [])

  const hideDevice = useCallback((mac) => {
    setHiddenMacs(prev => {
      const next = new Set(prev)
      if (next.has(mac)) next.delete(mac)
      else next.add(mac)
      try { localStorage.setItem('ns_hidden', JSON.stringify([...next])) } catch { /* ignore */ }
      return next
    })
  }, [])

  const clearHidden = useCallback(() => {
    setHiddenMacs(new Set())
    try { localStorage.removeItem('ns_hidden') } catch { /* ignore */ }
  }, [])

  // ── Derived ───────────────────────────────────────────────────────────────
  const online  = useMemo(() => devices.filter(d => d.is_online),            [devices])
  const trusted = useMemo(() => devices.filter(d => d.is_trusted),           [devices])
  const visible = useMemo(() => devices.filter(d => !hiddenMacs.has(d.mac)), [devices, hiddenMacs])
  const hidden  = useMemo(() => devices.filter(d =>  hiddenMacs.has(d.mac)), [devices, hiddenMacs])
  const unacked = useMemo(() => alerts.filter(a => !a.acked),                 [alerts])

  return {
    devices, visible, hidden, online, trusted, unsafe, status, alerts, unacked,
    scanning, scanMsg, connected, hiddenMacs,
    fetchAll, triggerScan, trustDevice, blockDevice, removeDevice,
    investigateDevice, ackAlert, ackAll, hideDevice, clearHidden,
    checkUpdates: api.checkUpdates,
    addDevice: api.addDevice,
  }
}
