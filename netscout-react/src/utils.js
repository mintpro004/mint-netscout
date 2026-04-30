export const HOT_PORTS = [21, 22, 23, 135, 137, 139, 445, 1433, 3306, 3389, 5900, 6379, 8080, 8443, 27017]

export function deviceIcon(d) {
  const v = (d?.vendor || d?.hostname || d?.alias || '').toLowerCase()
  if (v.includes('apple') || v.includes('iphone') || v.includes('ipad')) return '🍎'
  if (v.includes('samsung'))                                               return '📱'
  if (/router|gateway|ubiquiti|cisco|tp-link|netgear|asus/.test(v))      return '📡'
  if (/camera|hikvision|dahua/.test(v))                                   return '📷'
  if (/printer|hp|canon|epson/.test(v))                                   return '🖨️'
  if (/\btv\b|roku|chromecast|fire tv/.test(v))                           return '📺'
  if (/raspberry|arduino/.test(v))                                         return '🫐'
  if (/dell|lenovo|intel|microsoft/.test(v))                              return '💻'
  if (/google|nest/.test(v))                                               return '🏠'
  if (/sony|playstation|nintendo/.test(v))                                return '🎮'
  return '🔌'
}

export function fmtTime(ts) {
  if (!ts) return '--:--:--'
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function fmtAgo(ts) {
  if (!ts) return 'Never'
  const s = Math.floor(Date.now() / 1000 - ts)
  if (s < 5)    return 'Just now'
  if (s < 60)   return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

export function fmtMac(m) {
  return m ? m.toUpperCase() : '??:??:??:??:??:??'
}

export function isValidIPv4(ip) {
  return /^(25[0-5]|2[0-4]\d|[01]?\d\d?)\.(25[0-5]|2[0-4]\d|[01]?\d\d?)\.(25[0-5]|2[0-4]\d|[01]?\d\d?)\.(25[0-5]|2[0-4]\d|[01]?\d\d?)$/.test(ip)
}

export const SEV_COLOR = {
  critical: '#ff2255',
  high:     '#ff7700',
  medium:   '#ffcc00',
  warning:  '#ffcc00',
  info:     '#00ffaa',
  low:      '#00ffaa',
}

export function parsePorts(raw) {
  if (!raw) return []
  if (Array.isArray(raw)) return raw.map(p => typeof p === 'object' ? p : { port: p, service: '', risk: 'unknown' })
  try { return JSON.parse(raw).map(p => typeof p === 'object' ? p : { port: p, service: '', risk: 'unknown' }) }
  catch { return [] }
}
