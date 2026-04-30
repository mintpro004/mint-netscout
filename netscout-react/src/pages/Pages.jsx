import { Panel, PanelHeader, Tag, Badge, Btn } from '../components/ui'
import { fmtTime, fmtAgo, SEV_COLOR } from '../utils'
import styles from './Pages.module.css'

/* ── Threats ─────────────────────────────────────────────────────────────── */
export function Threats({ unsafe, onSelectDevice, onBlock }) {
  return (
    <Panel accent="red">
      <PanelHeader title="☣ Threat Intelligence Zone">
        <Tag variant="red">{unsafe.length} ACTIVE THREATS</Tag>
      </PanelHeader>
      <div className={styles.body}>
        {unsafe.length === 0 && (
          <div className={styles.empty}>NO MALICIOUS ACTIVITY DETECTED</div>
        )}
        {unsafe.map((u, i) => (
          <div key={i} className={styles.threatRow}>
            <div className={styles.threatIcon}>⚠️</div>
            <div className={styles.threatInfo}>
              <div className={styles.threatName}>THREAT: {u.threat}</div>
              <div className={styles.threatSub}>
                Source: {u.device?.ip || '—'} [{u.device?.hostname || 'UNKNOWN'}]
              </div>
              <div className={styles.threatActions}>
                <Btn variant="mint" size="sm" onClick={() => u.device && onSelectDevice(u.device.mac)}>
                  🔍 INVESTIGATE
                </Btn>
                <Btn variant="red" size="sm" onClick={() => u.device && onBlock(u.device.mac, true)}>
                  🚫 BLOCK
                </Btn>
              </div>
            </div>
            <div className={styles.xs}>{fmtTime(u.at)}</div>
          </div>
        ))}
      </div>
    </Panel>
  )
}

/* ── Alerts ──────────────────────────────────────────────────────────────── */
export function Alerts({ alerts, onAck }) {
  const unacked = alerts.filter(a => !a.acked)
  return (
    <Panel accent="red">
      <PanelHeader title="Alert Log">
        {unacked.length > 0 && <Tag variant="red">{unacked.length} UNACKNOWLEDGED</Tag>}
        {alerts.length > 0 && (
          <Btn variant="mint" size="sm" onClick={() => unacked.forEach(onAck)}>
            ACK ALL
          </Btn>
        )}
      </PanelHeader>
      <div className={styles.body}>
        {alerts.length === 0 && <div className={styles.empty}>NO ALERTS RECORDED</div>}
        {alerts.map((a, i) => {
          const col = SEV_COLOR[a.severity] || '#00ffaa'
          return (
            <div key={i} className={`${styles.alertItem} ${a.acked ? styles.acked : ''}`}>
              <div className={styles.alertBar} style={{ background: col }} />
              <div className={styles.alertBody}>
                <div className={styles.alertMsg}>{a.message}</div>
                <div className={styles.alertMeta}>
                  <Badge variant={a.severity === 'critical' ? 'danger' : a.severity === 'info' ? 'trusted' : 'warn'}>
                    {(a.severity || 'info').toUpperCase()}
                  </Badge>
                  {'  '}{fmtTime(a.timestamp)} · {a.device_ip || 'SYSTEM'}
                </div>
              </div>
              {!a.acked && (
                <button className={styles.ackBtn} onClick={() => onAck(a)}>✓ ACK</button>
              )}
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

/* ── Network ─────────────────────────────────────────────────────────────── */
export function Network({ status }) {
  return (
    <Panel accent="cyan">
      <PanelHeader title="Network Interfaces" />
      <div className={styles.body}>
        {!status && <div className={styles.empty}>LOADING NETWORK INFO…</div>}
        {status && (
          <>
            <div className={styles.detailRow}>
              <div className={styles.detailLbl}>Scan Permissions</div>
              <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <Badge variant={status.permissions?.has_raw_socket ? 'trusted' : 'warn'}>
                  {status.permissions?.has_raw_socket ? '✓ CAP_NET_RAW ACTIVE' : '⚠ LIMITED — ICMP ONLY'}
                </Badge>
                {status.permissions?.message && (
                  <div className={styles.xs}>{status.permissions.message}</div>
                )}
              </div>
            </div>
            {(status.networks || []).map((n, i) => (
              <div key={i} className={styles.detailRow}>
                <div className={styles.detailLbl}>Interface: {n.interface}</div>
                {[['Subnet', n.subnet], ['Local IP', n.ip || '—'], ['Gateway', n.gateway || '—']].map(([k, v]) => (
                  <div key={k} className={styles.netRow}>
                    <span className={styles.netKey}>{k}</span>
                    <span className={styles.netVal}>{v}</span>
                  </div>
                ))}
              </div>
            ))}
          </>
        )}
      </div>
    </Panel>
  )
}

/* ── Settings ────────────────────────────────────────────────────────────── */
export function Settings({ settings, setSettings, hiddenMacs, onClearHidden, onCheckUpdates, onExit, updLoading, connected, devices }) {
  return (
    <div className={styles.settingsGrid}>
      <Panel accent="mint" style={{ alignSelf: 'start' }}>
        <PanelHeader title="System Configuration" />
        <div className={styles.body}>
          {[
            { l: 'UI Animations', sub: 'Animated transitions and radar sweep', key: 'animations' },
            { l: 'Stealth Mode',  sub: 'Reduce active probing signatures',      key: 'stealth'    },
          ].map(s => (
            <div key={s.key} className={styles.settingRow}>
              <div>
                <div className={styles.settingLabel}>{s.l}</div>
                <div className={styles.settingSubLabel}>{s.sub}</div>
              </div>
              <div
                className={`${styles.toggle} ${settings[s.key] ? styles.toggleOn : ''}`}
                onClick={() => setSettings(p => ({ ...p, [s.key]: !p[s.key] }))}
              />
            </div>
          ))}

          <div className={styles.settingRow}>
            <div>
              <div className={styles.settingLabel}>Scan Frequency</div>
              <div className={styles.settingSubLabel}>Auto-discovery interval</div>
            </div>
            <select
              className={styles.select}
              value={settings.interval}
              onChange={e => setSettings(p => ({ ...p, interval: e.target.value }))}
            >
              <option value="30">AGGRESSIVE — 30s</option>
              <option value="120">BALANCED — 2m</option>
              <option value="600">STEALTH — 10m</option>
            </select>
          </div>

          <div className={styles.settingRow}>
            <div>
              <div className={styles.settingLabel}>Hidden Devices</div>
              <div className={styles.settingSubLabel}>{hiddenMacs.size} device(s) hidden</div>
            </div>
            <Btn variant="purple" size="sm" onClick={onClearHidden} disabled={hiddenMacs.size === 0}>
              REVEAL ALL
            </Btn>
          </div>
        </div>
      </Panel>

      <Panel accent="gold" style={{ alignSelf: 'start' }}>
        <PanelHeader title="System Info" />
        <div className={styles.body}>
          {[
            ['Version',    '2.1.0 PRO'],
            ['Developer',  'mintprojects'],
            ['Engine',     'Flask + SocketIO'],
            ['Database',   'SQLite ORM'],
            ['Protocol',   'ICMP + ARP + mDNS'],
            ['Connected',  connected ? 'WebSocket LIVE' : 'Polling fallback'],
            ['Total Seen', `${devices.length} devices`],
          ].map(([l, v]) => (
            <div key={l} className={styles.infoRow}>
              <span className={styles.infoLbl}>{l}</span>
              <span className={styles.infoVal}>{v}</span>
            </div>
          ))}
          <div className={styles.settingsBtns}>
            <Btn variant="gold" onClick={onCheckUpdates} disabled={updLoading} style={{ flex: 1 }}>
              {updLoading ? '⏳ CHECKING…' : '⟳ CHECK UPDATES'}
            </Btn>
            <Btn variant="red" onClick={onExit} style={{ flex: 1 }}>
              ⏻ SHUT DOWN
            </Btn>
          </div>
        </div>
      </Panel>
    </div>
  )
}
