import { X } from 'lucide-react'
import { useToasts } from '../hooks/useToast'
import styles from './ui.module.css'

/* ── Button ──────────────────────────────────────────────────────────────── */
export function Btn({ variant = 'mint', size = 'md', disabled, onClick, children, style, className = '' }) {
  return (
    <button
      className={`${styles.btn} ${styles[`btn-${variant}`]} ${styles[`btn-${size}`]} ${className}`}
      disabled={disabled}
      onClick={onClick}
      style={style}
    >
      {children}
    </button>
  )
}

/* ── Badge ───────────────────────────────────────────────────────────────── */
export function Badge({ variant = 'neutral', children }) {
  return <span className={`${styles.badge} ${styles[`badge-${variant}`]}`}>{children}</span>
}

/* ── Tag ─────────────────────────────────────────────────────────────────── */
export function Tag({ variant = 'mint', children }) {
  return <span className={`${styles.tag} ${styles[`tag-${variant}`]}`}>{children}</span>
}

/* ── Panel ───────────────────────────────────────────────────────────────── */
export function Panel({ accent = 'mint', children, className = '', style }) {
  return (
    <div className={`${styles.panel} ${styles[`pa-${accent}`]} ${className}`} style={style}>
      {children}
    </div>
  )
}

export function PanelHeader({ title, children }) {
  return (
    <div className={styles.panelHdr}>
      <span className={styles.panelTitle}>{title}</span>
      {children}
    </div>
  )
}

/* ── Modal overlay ───────────────────────────────────────────────────────── */
export function Modal({ onClose, width = 560, children }) {
  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose?.()}>
      <div className={styles.modal} style={{ width }}>
        {children}
      </div>
    </div>
  )
}

export function ModalHeader({ icon, title, subtitle, onClose }) {
  return (
    <div className={styles.modalHdr}>
      {icon && <div className={styles.modalIcon}>{icon}</div>}
      <div>
        <div className={styles.modalTitle}>{title}</div>
        {subtitle && <div className={styles.modalSub}>{subtitle}</div>}
      </div>
      <button className={styles.modalClose} onClick={onClose}><X size={14} /></button>
    </div>
  )
}

/* ── Input ───────────────────────────────────────────────────────────────── */
export function Input({ placeholder, value, onChange, style }) {
  return (
    <input
      className={styles.input}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      style={style}
    />
  )
}

/* ── Toggle ──────────────────────────────────────────────────────────────── */
export function Toggle({ on, onClick }) {
  return <div className={`${styles.toggle} ${on ? styles.toggleOn : ''}`} onClick={onClick} />
}

/* ── Toast layer ─────────────────────────────────────────────────────────── */
export function ToastLayer() {
  const { toasts, dismiss } = useToasts()
  return (
    <div className={styles.toastWrap}>
      {toasts.map(t => (
        <div key={t.id} className={`${styles.toast} ${styles[`toast-${t.type}`]}`} onClick={() => dismiss(t.id)}>
          {t.msg}
        </div>
      ))}
    </div>
  )
}

/* ── Status dot ──────────────────────────────────────────────────────────── */
export function Sdot({ online }) {
  return <span className={`${styles.sdot} ${online ? styles.sdotUp : styles.sdotDown}`} />
}

/* ── Port chip ───────────────────────────────────────────────────────────── */
const HOT = [21,22,23,135,137,139,445,1433,3306,3389,5900,6379,8080,8443,27017]
export function PortChip({ port, service }) {
  const hot = HOT.includes(+port)
  return (
    <span className={`${styles.pchip} ${hot ? styles.pchipHot : ''}`} title={service}>
      {port}{service ? ` (${service})` : ''}
    </span>
  )
}
