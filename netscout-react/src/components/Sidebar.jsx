import styles from './Sidebar.module.css'

const NAV = [
  { id: 'dashboard', glyph: '◈', label: 'Dashboard' },
  { id: 'devices',   glyph: '◉', label: 'Devices'   },
  { id: 'threats',   glyph: '☣', label: 'Threats'   },
  { id: 'alerts',    glyph: '△', label: 'Alerts'     },
  { id: 'network',   glyph: '◎', label: 'Network'    },
  { id: 'settings',  glyph: '⚙', label: 'Settings'  },
]

export default function Sidebar({
  view, setView,
  connected,
  isDark, onToggleTheme,
  threatCount, alertCount, hiddenCount,
  onAddDevice, onCheckUpdates, onClearHidden, onExit,
  updLoading,
}) {
  return (
    <aside className={styles.side}>
      <div className={styles.brand}>
        <div className={styles.logo}>MINT NETSCOUT</div>
        <div className={styles.tagline}>NETWORK INTELLIGENCE SYSTEM</div>
        <div className={styles.ver}>v2.1 PRO</div>
      </div>

      <div className={styles.sectionLabel}>Operations</div>
      {NAV.map(n => (
        <div
          key={n.id}
          className={`${styles.navItem} ${view === n.id ? styles.active : ''}`}
          onClick={() => setView(n.id)}
        >
          <span className={styles.glyph}>{n.glyph}</span>
          {n.label}
          {n.id === 'threats' && threatCount > 0 && <span className={styles.badge}>{threatCount}</span>}
          {n.id === 'alerts'  && alertCount  > 0 && <span className={styles.badge}>{alertCount}</span>}
        </div>
      ))}

      <div className={styles.sectionLabel}>System Tools</div>
      <div className={styles.navItem} onClick={onToggleTheme}>
        <span className={styles.glyph}>{isDark ? '☀' : '🌙'}</span> 
        {isDark ? 'Light Mode' : 'Dark Mode'}
      </div>
      <div className={styles.navItem} onClick={onAddDevice}>
        <span className={styles.glyph}>✚</span> Add Asset
      </div>
      <div
        className={styles.navItem}
        onClick={updLoading ? undefined : onCheckUpdates}
        style={updLoading ? { opacity: 0.5, cursor: 'not-allowed' } : {}}
      >
        <span className={styles.glyph}>{updLoading ? '⏳' : '⟳'}</span>
        {updLoading ? 'Checking…' : 'Check Updates'}
      </div>
      {hiddenCount > 0 && (
        <div className={styles.navItem} style={{ color: 'var(--purple)' }} onClick={onClearHidden}>
          <span className={styles.glyph}>👁</span>
          Unhide All ({hiddenCount})
        </div>
      )}

      <div className={styles.bottom}>
        <div className={styles.connRow}>
          <span className={`${styles.dot} ${connected ? '' : styles.dotOff}`} />
          {connected ? 'SYSTEM ONLINE' : 'DISCONNECTED'}
        </div>
        <button className={styles.exitBtn} onClick={onExit}>
          ⏻ SHUT DOWN
        </button>
      </div>
    </aside>
  )
}
