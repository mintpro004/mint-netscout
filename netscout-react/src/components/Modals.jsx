import { useState } from 'react'
import { Modal, ModalHeader, Btn, Input } from './ui'
import { isValidIPv4 } from '../utils'
import { toast } from '../hooks/useToast'
import styles from './Modals.module.css'

/* ── Add Device Modal ────────────────────────────────────────────────────── */
export function AddDeviceModal({ onClose, onAdd }) {
  const [form, setForm] = useState({ ip: '', mac: '', hostname: '', type: 'unknown' })
  const [loading, setLoading] = useState(false)

  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }))

  const handleSubmit = async () => {
    if (!form.ip) { toast.error('IP address is required'); return }
    if (!isValidIPv4(form.ip)) { toast.error('Invalid IPv4 address format'); return }
    setLoading(true)
    try {
      const res = await onAdd(form)
      if (res?.success) { toast.success('Asset registered successfully'); onClose() }
      else toast.error('Error: ' + (res?.error || 'Unknown error'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal onClose={onClose} width={420}>
      <ModalHeader title="ADD ASSET MANUALLY" onClose={onClose} />
      <div className={styles.body}>
        <Input placeholder="IP Address *"      value={form.ip}       onChange={set('ip')} />
        <Input placeholder="MAC Address"       value={form.mac}      onChange={set('mac')} />
        <Input placeholder="Hostname"          value={form.hostname} onChange={set('hostname')} />
        <div className={styles.row}>
          <Btn variant="mint" style={{ flex: 1 }} onClick={handleSubmit} disabled={loading}>
            {loading ? '⏳ REGISTERING…' : 'REGISTER ASSET'}
          </Btn>
          <Btn variant="ghost" onClick={onClose}>CANCEL</Btn>
        </div>
      </div>
    </Modal>
  )
}

/* ── Update Modal ────────────────────────────────────────────────────────── */
export function UpdateModal({ info, onClose, onApply }) {
  return (
    <Modal onClose={onClose} width={460}>
      <ModalHeader title="SYSTEM UPDATE" onClose={onClose} />
      <div className={styles.body}>
        {info.update_available ? (
          <>
            <div className={styles.updateVer}>⬆ NEW VERSION: {info.latest_version}</div>
            <div className={styles.updateCur}>INSTALLED: {info.current_version}</div>
            <div className={styles.changelogBox}>
              <div className={styles.changelogTitle}>CHANGELOG</div>
              {(info.changelog || []).map((c, i) => (
                <div key={i} className={styles.changelogItem}>• {c}</div>
              ))}
            </div>
            <Btn variant="mint" style={{ width: '100%' }} onClick={onApply}>
              ⬇ DOWNLOAD & INSTALL v{info.latest_version}
            </Btn>
          </>
        ) : (
          <div className={styles.upToDate}>
            <div className={styles.upToDateIcon}>✓</div>
            <div className={styles.upToDateTitle}>SYSTEM UP TO DATE</div>
            <div className={styles.upToDateSub}>VERSION: {info.current_version}</div>
          </div>
        )}
      </div>
    </Modal>
  )
}

/* ── Exit Modal ──────────────────────────────────────────────────────────── */
export function ExitModal({ onClose, onConfirm }) {
  return (
    <Modal onClose={onClose} width={380}>
      <div className={styles.exitBody}>
        <div className={styles.exitIcon}>⚡</div>
        <div className={styles.exitTitle}>TERMINATE SESSION</div>
        <div className={styles.exitSub}>SHUT DOWN MINT NETSCOUT AND CLOSE THE DASHBOARD?</div>
        <div className={styles.row}>
          <Btn variant="mint" onClick={onClose} style={{ flex: 1 }}>◀ ABORT</Btn>
          <Btn variant="red"  onClick={onConfirm} style={{ flex: 1 }}>⏻ SHUT DOWN</Btn>
        </div>
      </div>
    </Modal>
  )
}
