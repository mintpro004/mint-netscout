import { useState, useMemo } from 'react'
import { Modal, ModalHeader, Btn, Badge, PortChip } from './ui'
import { deviceIcon, fmtMac, fmtTime, fmtAgo, parsePorts } from '../utils'
import styles from './DeviceModal.module.css'

const RISK_COLOR = { critical: '#ff2255', high: '#ff7700', medium: '#ffcc00', low: '#00ffaa', none: '#00ffaa' }

export default function DeviceModal({ mac, devices, onClose, onInvestigate, onBlock, onRemove, onHide }) {
  const [investResult, setInvestResult] = useState(null)
  const [investing,    setInvesting]    = useState(false)
  const [blocking,     setBlocking]     = useState(false)
  const [removing,     setRemoving]     = useState(false)

  // Always reflect latest device state from live list
  const dev = useMemo(
    () => (mac ? devices.find(d => d.mac === mac) : null) || null,
    [devices, mac]
  )

  const ports    = useMemo(() => parsePorts(dev?.open_ports || '[]'), [dev?.open_ports])
  const isBlocked = dev?.is_blocked
  const isTrusted = dev?.is_trusted

  if (!dev) return null

  const handleInvestigate = async () => {
    setInvesting(true)
    const res = await onInvestigate(dev.mac)
    setInvestResult(res)
    setInvesting(false)
  }

  const handleBlock = async () => {
    setBlocking(true)
    await onBlock(dev.mac, !isBlocked)
    setBlocking(false)
  }

  const handleRemove = async () => {
    if (!confirm(`Remove ${dev.alias || dev.hostname || dev.ip} from registry?`)) return
    setRemoving(true)
    const res = await onRemove(dev.mac)
    if (res?.success) onClose()
    else setRemoving(false)
  }

  const rl = investResult?.risk?.level || 'none'
  const rc = RISK_COLOR[rl] || '#00ffaa'

  return (
    <Modal onClose={onClose}>
      <ModalHeader
        icon={deviceIcon(dev)}
        title={dev.alias || dev.hostname || dev.ip}
        subtitle={`${dev.vendor || 'Unknown Vendor'} · ${fmtMac(dev.mac)}`}
        onClose={onClose}
      />

      <div className={styles.body}>
        {/* Detail grid */}
        <div className={styles.grid}>
          {[
            ['IP Address',   dev.ip || '—'],
            ['MAC Address',  fmtMac(dev.mac)],
            ['Alias',        dev.alias || '—'],
            ['Hostname',     dev.hostname || '—'],
            ['Vendor',       dev.vendor || '—'],
            ['OS Hint',      dev.os_hint || '—'],
            ['Device Type',  dev.device_type || '—'],
            ['First Seen',   fmtTime(dev.first_seen)],
            ['Last Seen',    fmtAgo(dev.last_seen)],
            ['Latency',      dev.latency_ms ? `${dev.latency_ms.toFixed(1)} ms` : '—'],
            ['Traffic IN',   `${(dev.traffic_in  || 0).toFixed(2)} MB`],
            ['Traffic OUT',  `${(dev.traffic_out || 0).toFixed(2)} MB`],
          ].map(([l, v]) => (
            <div key={l} className={styles.detail}>
              <div className={styles.detailLbl}>{l}</div>
              <div className={styles.detailVal}>{v}</div>
            </div>
          ))}
        </div>

        {/* Status badges */}
        <div className={styles.detail} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <div className={styles.detailLbl} style={{ width: '100%' }}>Device Status</div>
          <Badge variant={isTrusted ? 'trusted' : 'warn'}>
            {isTrusted ? '✓ TRUSTED' : '⚠ UNVERIFIED'}
          </Badge>
          <Badge variant={dev.is_online ? 'online' : 'offline'}>
            {dev.is_online ? '● ONLINE' : '○ OFFLINE'}
          </Badge>
          {isBlocked && <Badge variant="danger">🚫 BLOCKED (RESTRICTED)</Badge>}
        </div>

        {/* Open ports */}
        {ports.length > 0 && (
          <div className={styles.detail}>
            <div className={styles.detailLbl}>Open Ports ({ports.length})</div>
            <div className={styles.portRow}>
              {ports.map((p, i) => (
                <PortChip key={`${i}_${p.port}`} port={p.port} service={p.service} />
              ))}
            </div>
          </div>
        )}

        {/* Investigation results */}
        {investResult?.success && (
          <div className={styles.investResult}>
            <div className={styles.investTitle}>Investigation Results</div>
            <div
              className={styles.riskBadge}
              style={{ color: rc, borderColor: rc, background: rc + '20' }}
            >
              Risk: {rl.toUpperCase()}
            </div>
            {investResult.risk?.reason && (
              <div className={styles.investSub}>{investResult.risk.reason}</div>
            )}
            {investResult.ports?.length > 0 ? (
              <div className={styles.portRow}>
                {investResult.ports.map((p, i) => (
                  <PortChip key={`inv_${i}`} port={typeof p === 'object' ? p.port : p} service={typeof p === 'object' ? p.service : ''} />
                ))}
              </div>
            ) : (
              <div className={styles.investSub}>No open ports detected</div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className={styles.actions}>
          <Btn variant="mint" onClick={handleInvestigate} disabled={investing}>
            {investing ? '⏳ Scanning…' : '🔍 Investigate'}
          </Btn>
          <Btn variant={isBlocked ? 'gold' : 'red'} onClick={handleBlock} disabled={blocking}>
            {blocking ? '⏳ Wait…' : isBlocked ? '🔓 Unblock' : '🚫 Block'}
          </Btn>
          <Btn variant="purple" onClick={() => { onHide(dev.mac); onClose() }}>
            👁 Hide
          </Btn>
          <Btn variant="red" style={{ marginLeft: 'auto' }} onClick={handleRemove} disabled={removing}>
            {removing ? '⏳ Removing…' : '🗑 Remove'}
          </Btn>
        </div>
      </div>
    </Modal>
  )
}
