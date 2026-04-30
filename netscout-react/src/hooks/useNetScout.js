import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { api, createSocket } from '../api'

export function useNetScout() {
  const [devices,   setDevices]   = useState([])
  const [unsafe,    setUnsafe]    = useState([])
  const [status,    setStatus]    = useState(null)
  const [alerts,    setAlerts]    = useState([])
  const [scanning,  setScanning]  = useState(false)
  const [scanMsg,   setScanMsg]   = useState('')
  const [connected, setConnected] = useState(false)
  const [hiddenMacs, setHiddenMacs] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem('ns_hidden') || '[]')) }
    catch { return new Set() }
  })

  const sockRef  = useRef(null)
  const pollRef  = useRef(null)

  // ── Independent fetches so one failure doesn't wipe all data ──────────────
  const fetchAll = useCallback(async () => {
    api.getDevices().then(d => setDevices(d.devices || [])).catch(console.warn)
    api.getUnsafe().then(u => setUnsafe(u.unsafe_zone || [])).catch(console.warn)
    api.getStatus().then(setStatus).catch(console.warn)
  }, [])

  // ── Socket setup ──────────────────────────────────────────────────────────
  useEffect(() => {
    const sock = createSocket()
    sockRef.current = sock

    sock.on('connect',        () => { setConnected(true);  fetchAll() })
    sock.on('disconnect',     () => setConnected(false))
    sock.on('scan_progress',  d  => { setScanning(true);  setScanMsg(d.message || 'Scanning…') })
    sock.on('scan_complete',  d  => {
      setScanning(false); setScanMsg('')
      if (d.devices) setDevices(d.devices)
      else fetchAll()
    })
    sock.on('scan_error',     () => { setScanning(false);  setScanMsg('') })
    sock.on('alert',          a  => setAlerts(p => [a, ...p].slice(0, 200)))

    fetchAll()
    pollRef.current = setInterval(fetchAll, 20_000)

    return () => {
      sock.disconnect()
      clearInterval(pollRef.current)
    }
  }, [fetchAll])

  // ── Actions ───────────────────────────────────────────────────────────────
  const triggerScan = useCallback(async (aggressive = false) => {
    setScanning(true)
    setScanMsg(aggressive ? 'Initiating AGGRESSIVE deep discovery…' : 'Initiating standard discovery…')
    try { await api.triggerScan(aggressive) }
    catch { setScanning(false); setScanMsg('') }
  }, [])

  const trustDevice = useCallback(async (mac, trusted) => {
    const res = await api.trustDevice(mac, trusted)
    if (res.success) setDevices(p => p.map(d => d.mac === mac ? { ...d, is_trusted: trusted } : d))
    return res
  }, [])

  const blockDevice = useCallback(async (mac, blocked) => {
    const res = await api.blockDevice(mac, blocked)
    if (res.success) setDevices(p => p.map(d => d.mac === mac ? { ...d, is_trusted: !blocked } : d))
    return res
  }, [])

  const removeDevice = useCallback(async (mac) => {
    const res = await api.removeDevice(mac)
    if (res.success) setDevices(p => p.filter(d => d.mac !== mac))
    return res
  }, [])

  const investigateDevice = useCallback(async (mac) => {
    setScanning(true); setScanMsg('Running deep port investigation…')
    try {
      const res = await api.investigateDevice(mac)
      setScanning(false); setScanMsg('')
      if (res.success) setDevices(p => p.map(d => d.mac === mac ? { ...d, open_ports: res.ports || [] } : d))
      return res
    } catch {
      setScanning(false); setScanMsg('')
      return null
    }
  }, [])

  const ackAlert = useCallback((a) => {
    setAlerts(p => p.map(x =>
      x.timestamp === a.timestamp && x.device_ip === a.device_ip && x.alert_type === a.alert_type
        ? { ...x, acked: true } : x
    ))
  }, [])

  const hideDevice = useCallback((mac) => {
    setHiddenMacs(prev => {
      const next = new Set(prev)
      if (next.has(mac)) next.delete(mac)
      else next.add(mac)
      try { localStorage.setItem('ns_hidden', JSON.stringify([...next])) } catch (err) { console.error(err) }
      return next
    })
  }, [])

  const clearHidden = useCallback(() => {
    setHiddenMacs(new Set())
    try { localStorage.removeItem('ns_hidden') } catch (err) { console.error(err) }
  }, [])

  // ── Derived state ─────────────────────────────────────────────────────────
  const online   = useMemo(() => devices.filter(d => d.is_online),   [devices])
  const trusted  = useMemo(() => devices.filter(d => d.is_trusted),  [devices])
  const visible  = useMemo(() => devices.filter(d => !hiddenMacs.has(d.mac)), [devices, hiddenMacs])
  const hidden   = useMemo(() => devices.filter(d =>  hiddenMacs.has(d.mac)), [devices, hiddenMacs])
  const unacked  = useMemo(() => alerts.filter(a => !a.acked),        [alerts])

  return {
    devices, visible, hidden, online, trusted, unsafe, status, alerts, unacked,
    scanning, scanMsg, connected, hiddenMacs,
    fetchAll, triggerScan, trustDevice, blockDevice, removeDevice,
    investigateDevice, ackAlert, hideDevice, clearHidden,
    checkUpdates: api.checkUpdates,
    addDevice: api.addDevice,
  }
}
