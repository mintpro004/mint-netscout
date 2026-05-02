import { Panel, PanelHeader, Tag, Badge, Btn } from '../components/ui'
import { fmtTime, SEV_COLOR } from '../utils'
import styles from './Pages.module.css'

/* ── Threats ─────────────────────────────────────────────────────────────── */
export function Threats({ unsafe, history, onSelectDevice, onBlock, onMark }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <Panel accent="red">
        <PanelHeader title="☣ Threat Intelligence Zone">
          <Tag variant="red">{unsafe.length} ACTIVE THREATS</Tag>
        </PanelHeader>
        <div className={styles.body}>
          {unsafe.length === 0 && (
            <div className={styles.empty}>NO MALICIOUS ACTIVITY DETECTED</div>
          )}
          {unsafe.map((u, i) => {
            const devMac = u.device?.mac
            const devIp  = u.device?.ip   || '—'
            const devHost = u.device?.hostname || 'UNKNOWN'
            return (
              <div key={i} className={styles.threatRow}>
                <div className={styles.threatIcon}>⚠️</div>
                <div className={styles.threatInfo}>
                  <div className={styles.threatName}>THREAT: {u.threat}</div>
                  <div className={styles.threatSub}>
                    Source: {devIp} [{devHost}]
                  </div>
                  <div className={styles.threatActions}>
                    <Btn
                      variant="mint" size="sm"
                      onClick={() => devMac && onSelectDevice(devMac)}
                      disabled={!devMac}
                    >
                      🔍 INVESTIGATE
                    </Btn>
                    <Btn
                      variant="red" size="sm"
                      onClick={() => devMac && onBlock(devMac, true)}
                      disabled={!devMac}
                    >
                      🚫 BLOCK
                    </Btn>
                    <Btn
                      variant="gold" size="sm"
                      onClick={() => onMark(u.threat, 'safe')}
                    >
                      🛡 MARK SAFE
                    </Btn>
                  </div>
                </div>
                <div className={styles.xs}>{fmtTime(u.at)}</div>
              </div>
            )
          })}
        </div>
      </Panel>

      <Panel accent="cyan">
        <PanelHeader title="🌐 Real-time Traffic Analysis (Safe/Unsafe Zone)">
          <Tag variant="mint">{history.length} RECENT VISITS</Tag>
        </PanelHeader>
        <div className={styles.body}>
          {history.length === 0 && (
            <div className={styles.empty}>STILL SNIFFING PACKETS…</div>
          )}
          {history.map((h, i) => (
            <div key={i} className={styles.threatRow} style={{ borderBottom: '1px solid #ffffff10', paddingBottom: 10 }}>
              <div className={styles.threatIcon}>{h.is_malicious ? '💀' : '🌐'}</div>
              <div className={styles.threatInfo}>
                <div className={styles.threatName} style={{ color: h.is_malicious ? '#ff2255' : '#00ffaa' }}>
                  {h.domain}
                  {h.is_malicious && <span style={{ marginLeft: 10, fontSize: 10, color: '#ff2255', verticalAlign: 'middle' }}>[THREAT DETECTED]</span>}
                </div>
                <div className={styles.threatSub}>
                  Device: <span style={{ color: 'var(--mint)' }}>{h.device?.alias || h.device?.hostname || h.device?.ip || 'Unknown'}</span>
                  {h.device?.mac && <span style={{ marginLeft: 8, opacity: 0.6 }}>({h.device.mac})</span>}
                </div>
              </div>
              <div className={styles.threatActions} style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
                <div className={styles.xs} style={{ minWidth: 80, textAlign: 'right', opacity: 0.7 }}>{fmtTime(h.timestamp)}</div>
                <Btn
                  variant={h.is_malicious ? 'mint' : 'red'} size="xs"
                  onClick={() => onMark(h.domain, h.is_malicious ? 'safe' : 'unsafe')}
                >
                  {h.is_malicious ? 'TRUST' : 'BAN'}
                </Btn>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

/* ── Alerts ──────────────────────────────────────────────────────────────── */
// FIX: accept onAckAll prop and use _id-based keying
export function Alerts({ alerts, onAck, onAckAll }) {
  const unacked = alerts.filter(a => !a.acked)
  return (
    <Panel accent="red">
      <PanelHeader title="Alert Log">
        {unacked.length > 0 && <Tag variant="red">{unacked.length} UNACKNOWLEDGED</Tag>}
        {alerts.length > 0 && (
          <Btn variant="mint" size="sm" onClick={onAckAll}>
            ACK ALL
          </Btn>
        )}
      </PanelHeader>
      <div className={styles.body}>
        {alerts.length === 0 && <div className={styles.empty}>NO ALERTS RECORDED</div>}
        {alerts.map(a => {
          const col = SEV_COLOR[a.severity] || '#00ffaa'
          return (
            <div key={a._id} className={`${styles.alertItem} ${a.acked ? styles.acked : ''}`}>
              <div className={styles.alertBar} style={{ background: col }} />
              <div className={styles.alertBody}>
                <div className={styles.alertMsg}>{a.message}</div>
                <div className={styles.alertMeta}>
                  <Badge variant={
                    a.severity === 'critical' ? 'danger' :
                    a.severity === 'info'     ? 'trusted' : 'warn'
                  }>
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
                  {status.permissions?.has_raw_socket
                    ? '✓ CAP_NET_RAW ACTIVE'
                    : '⚠ LIMITED — ICMP ONLY'}
                </Badge>
                {status.permissions?.message && (
                  <div className={styles.xs}>{status.permissions.message}</div>
                )}
              </div>
            </div>
            {(status.networks || []).map((n, i) => (
              <div key={i} className={styles.detailRow}>
                <div className={styles.detailLbl}>Interface: {n.interface}</div>
                {[
                  ['Subnet',   n.subnet],
                  ['Local IP', n.ip      || '—'],
                  ['Gateway',  n.gateway || '—'],
                ].map(([k, v]) => (
                  <div key={k} className={styles.netRow}>
                    <span className={styles.netKey}>{k}</span>
                    <span className={styles.netVal}>
                      {v}
                      {k === 'Gateway' && v !== '—' && (
                        <a 
                          href={`http://${v}`} 
                          target="_blank" 
                          rel="noreferrer"
                          style={{ marginLeft: 10, fontSize: '0.8em', color: '#00ffaa', textDecoration: 'underline' }}
                        >
                          [OPEN ADMIN]
                        </a>
                      )}
                    </span>
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
export function Settings({
  settings, setSettings, hiddenMacs, onClearHidden,
  onCheckUpdates, onExit, updLoading, connected, devices
}) {
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
              <div className={styles.settingSubLabel}>{hiddenMacs.size} device(s) hidden from view</div>
            </div>
            <Btn
              variant="purple" size="sm"
              onClick={onClearHidden}
              disabled={hiddenMacs.size === 0}
            >
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
            ['Connection', connected ? '🟢 WebSocket LIVE' : '🔴 Polling fallback'],
            ['Devices Known', `${devices.length}`],
          ].map(([l, v]) => (
            <div key={l} className={styles.infoRow}>
              <span className={styles.infoLbl}>{l}</span>
              <span className={styles.infoVal}>{v}</span>
            </div>
          ))}
          <div className={styles.settingsBtns}>
            <Btn
              variant="gold"
              onClick={onCheckUpdates}
              disabled={updLoading}
              style={{ flex: 1 }}
            >
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
