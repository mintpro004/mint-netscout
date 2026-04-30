import { useState, useEffect } from 'react'
import styles from './Topbar.module.css'

export default function Topbar({ onlineCount, totalCount, trustedCount, threatCount, connected, scanning, onScan, onAggressiveScan }) {
  const [clock, setClock] = useState(() =>
    new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  )

  useEffect(() => {
    const id = setInterval(() => {
      setClock(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    }, 1000)
    return () => clearInterval(id)
  }, [])

  const metrics = [
    { label: 'TOTAL ASSETS', value: totalCount },
    { label: 'ONLINE',       value: onlineCount },
    { label: 'TRUSTED',      value: trustedCount },
    { label: 'THREATS',      value: threatCount  },
  ]

  return (
    <header className={styles.top}>
      <div className={styles.metrics}>
        {metrics.map(m => (
          <div key={m.label} className={styles.metric}>
            <div className={styles.metricVal}>{m.value}</div>
            <div className={styles.metricLbl}>{m.label}</div>
          </div>
        ))}
      </div>

      <div className={styles.right}>
        <div className={styles.clock}>{clock}</div>

        <div className={`${styles.chip} ${connected ? styles.chipLive : styles.chipDead}`}>
          <span className={styles.chipDot} />
          {connected ? 'LIVE FEED' : 'OFFLINE'}
        </div>

        <button
          className={`${styles.scanBtn} ${scanning ? styles.scanning : ''}`}
          onClick={() => !scanning && onScan(false)}
          disabled={scanning}
        >
          <span>{scanning ? '◈' : '▶'}</span>
          {scanning ? 'PROBING…' : 'DEEP SCAN'}
        </button>

        <button
          className={`${styles.scanBtn} ${styles.scanBtnRed} ${scanning ? styles.scanning : ''}`}
          onClick={() => !scanning && onScan(true)}
          disabled={scanning}
        >
          <span>☢</span>
          {scanning ? 'SCANNING…' : 'AGGRESSIVE'}
        </button>
      </div>
    </header>
  )
}
