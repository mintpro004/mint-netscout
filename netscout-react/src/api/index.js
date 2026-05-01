import { io } from 'socket.io-client'

const BASE = ''   // same-origin; Vite proxy handles /api in dev

// ─── REST helpers ─────────────────────────────────────────────────────────────

async function get(path) {
  const r = await fetch(BASE + path)
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`)
  return r.json()
}

async function post(path, body) {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(`POST ${path} → ${r.status}`)
  return r.json()
}

async function del(path) {
  const r = await fetch(BASE + path, { method: 'DELETE' })
  if (!r.ok) throw new Error(`DELETE ${path} → ${r.status}`)
  return r.json()
}

// ─── Device API ───────────────────────────────────────────────────────────────

export const api = {
  getDevices:      ()          => get('/api/devices'),
  getStatus:       ()          => get('/api/status'),
  getUnsafe:       ()          => get('/api/intel/unsafe'),
  getIntelHistory: ()          => get('/api/intel/history'),
  checkUpdates:    ()          => get('/api/update/check'),

  addDevice:       (data)      => post('/api/devices/add', data),
  triggerScan:     (aggressive) => post('/api/scan', { aggressive }),
  trustDevice:     (mac, trusted)  => post(`/api/devices/${encodeURIComponent(mac)}/trust`, { trusted }),
  blockDevice:     (mac, blocked)  => post(`/api/devices/${encodeURIComponent(mac)}/block`, { blocked }),
  investigateDevice: (mac)     => post(`/api/devices/${encodeURIComponent(mac)}/investigate`),
  registerDevice:  (mac, alias) => post(`/api/devices/${encodeURIComponent(mac)}/register`, { alias }),
  markIntel:       (domain, status) => post('/api/intel/mark', { domain, status }),
  removeDevice:    (mac)       => del(`/api/devices/${encodeURIComponent(mac)}`),
}

// ─── Socket ───────────────────────────────────────────────────────────────────

export function createSocket() {
  return io(window.location.origin, {
    transports: ['websocket', 'polling'],
    reconnectionDelay: 3000,
    reconnectionDelayMax: 10000,
  })
}
