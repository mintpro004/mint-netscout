import { useMemo } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Panel, PanelHeader, Tag } from '../components/ui'
import { deviceIcon, fmtAgo, SEV_COLOR } from '../utils'
import styles from './Dashboard.module.css'

/* ── Radar ───────────────────────────────────────────────────────────────── */
function Radar({ devices, scanning, onSelect }) {
  const online = useMemo(() => devices.filter(d => d.is_online), [devices])

  // Optimization: Reduce number of dots on radar for Chromebook performance
  const dots = useMemo(() =>
    online.slice(0, 15).map((d, i) => {
      const angle = (i / Math.max(online.length, 1)) * Math.PI * 2 - Math.PI / 2 + (i % 4) * 0.22
      const r = 25 + (i % 4) * 10
      return { x: 50 + r * Math.cos(angle), y: 50 + r * Math.sin(angle), d }
    }), [online])

  return (
    <div className={styles.radarWrap}>
      <div className={styles.radarCanvas}>
        {[80, 60, 40, 20].map(s => (
          <div key={s} className={styles.ring} style={{ width: `${s}%`, height: `${s}%` }} />
        ))}
        <div className={styles.cross} />
        {/* Only show sweep if scanning to save CPU */}
        {scanning && (
          <div className={styles.sweepWrap}><div className={styles.arm} /></div>
        )}
        <div className={styles.center} />
        {dots.map(({ x, y, d }) => (
          <div
            key={d.mac || d.ip}
            className={styles.dot}
            style={{ left: `${x}%`, top: `${y}%` }}
            title={d.alias || d.hostname || d.ip}
            onClick={() => onSelect(d.mac || d.ip)} 
          />
        ))}
      </div>

      <div className={styles.radarList}>
        {online.slice(0, 9).map(d => (
          <div
            key={d.mac || d.ip}
            className={styles.radarRow}
            onClick={() => onSelect(d.mac || d.ip)}  // FIX: pass MAC string
          >
            <span className={styles.radarIcon}>{deviceIcon(d)}</span>
            <div className={styles.radarInfo}>
              <div className={styles.radarName}>{d.alias || d.hostname || d.ip}</div>
              <div className={styles.radarIp}>{d.ip}</div>
            </div>
            <span className={styles.liveDot} />
          </div>
        ))}
        {online.length === 0 && (
          <div className={styles.empty}>NO LIVE ASSETS</div>
        )}
      </div>
    </div>
  )
}

/* ── Chart tooltip ───────────────────────────────────────────────────────── */
function ChartTip({ active, payload }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--b2)',
      borderRadius: 6, padding: '5px 10px',
      fontFamily: 'var(--f-data)', fontSize: 10, color: 'var(--mint)'
    }}>
      {(payload[0].value || 0).toFixed(1)} ms
    </div>
  )
}

/* ── Dashboard ───────────────────────────────────────────────────────────── */
export default function Dashboard({
  visible, online, trusted, unsafe, alerts, status,
  scanning, hiddenMacs, onSelectDevice, onAck
}) {
  const latData = useMemo(() =>
    online
      .filter(d => d.latency_ms > 0)
      .slice(0, 40)
      .map((d, i) => ({ t: i, ms: d.latency_ms }))
  , [online])

  const unacked = alerts.filter(a => !a.acked)

  const kpis = [
    {
      icon: '🔌', lbl: 'Total Assets', kc: 'var(--mint)',
      val: visible.length,
      sub: `${online.filter(d => !hiddenMacs.has(d.mac)).length} online`,
    },
    {
      icon: '📶', lbl: 'Live Devices', kc: 'var(--cyan)',
      val: online.filter(d => !hiddenMacs.has(d.mac)).length,
      sub: `${visible.length - online.filter(d => !hiddenMacs.has(d.mac)).length} offline`,
    },
    {
      icon: '☣',  lbl: 'Threats', kc: 'var(--red)',
      val: unsafe.length,
      sub: 'active detections',
    },
    {
      icon: '🛡',  lbl: 'Trusted', kc: 'var(--gold)',
      val: trusted.filter(d => !hiddenMacs.has(d.mac)).length,
      sub: `${visible.length - trusted.filter(d => !hiddenMacs.has(d.mac)).length} unverified`,
    },
  ]

  return (
    <div className={styles.wrap}>
      {/* KPIs */}
      <div className={styles.kpiGrid}>
        {kpis.map(k => (
          <div key={k.lbl} className={styles.kpi} style={{ '--kc': k.kc }}>
            <div className={styles.kpiIcon}>{k.icon}</div>
            <div className={styles.kpiVal} style={{ color: k.kc }}>{k.val}</div>
            <div className={styles.kpiLbl}>{k.lbl}</div>
            <div className={styles.kpiSub}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* Radar + Alert feed */}
      <div className={styles.row73}>
        <Panel accent="mint">
          <PanelHeader title="Network Topology">
            {scanning && <Tag variant="gold">◈ SWEEPING</Tag>}
          </PanelHeader>
          <div className={styles.panelBody}>
            <Radar devices={visible} scanning={scanning} onSelect={onSelectDevice} />
          </div>
        </Panel>

        <Panel accent="red">
          <PanelHeader title="Alert Feed">
            {unacked.length > 0 && <Tag variant="red">{unacked.length} NEW</Tag>}
          </PanelHeader>
          <div className={styles.alertList}>
            {alerts.slice(0, 7).map(a => {
              const col = SEV_COLOR[a.severity] || '#00ffaa'
              return (
                <div key={a._id} className={`${styles.alertItem} ${a.acked ? styles.acked : ''}`}>
                  <div className={styles.alertBar} style={{ background: col }} />
                  <div className={styles.alertBody}>
                    <div className={styles.alertMsg}>{a.message}</div>
                    <div className={styles.alertMeta}>
                      {fmtAgo(a.timestamp)} · {a.device_ip || '—'}
                    </div>
                  </div>
                  {!a.acked && (
                    <button className={styles.ackBtn} onClick={() => onAck(a)}>ACK</button>
                  )}
                </div>
              )
            })}
            {alerts.length === 0 && (
              <div className={styles.empty}>NO ALERTS DETECTED</div>
            )}
          </div>
        </Panel>
      </div>

      {/* System info + Latency chart */}
      <div className={styles.row2}>
        <Panel accent="gold">
          <PanelHeader title="System Intelligence" />
          <div className={styles.panelBody}>
            {[
              ['Version',       status?.version || '2.1.0 PRO'],
              ['CPU Load',      status?.system_load !== undefined ? `${status.system_load}%` : '—'],
              ['Networks',      (status?.networks || []).map(n => n.subnet).join(', ') || '—'],
              ['Permissions',   status?.permissions?.has_raw_socket ? '✓ CAP_NET_RAW' : '⚠ ICMP Only'],
              ['Hidden Assets', hiddenMacs.size > 0 ? `${hiddenMacs.size} hidden` : 'None'],
            ].map(([l, v]) => (
              <div key={l} className={styles.infoRow}>
                <span className={styles.infoLbl}>{l}</span>
                <span className={styles.infoVal}>{v}</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel accent="cyan">
          <PanelHeader title="Gateway Analysis" />
          <div className={styles.panelBody}>
            {!status?.networks?.[0]?.gateway ? (
              <div className={styles.empty}>IDENTIFYING GATEWAY...</div>
            ) : (
              <>
                <div className={styles.infoRow}>
                  <span className={styles.infoLbl}>IP Address</span>
                  <span className={styles.infoVal} style={{ color: 'var(--cyan)' }}>{status.networks[0].gateway}</span>
                </div>
                <div className={styles.infoRow}>
                  <span className={styles.infoLbl}>Model</span>
                  <span className={styles.infoVal}>{routerInfo?.model || 'Analyzing...'}</span>
                </div>
                <div className={styles.infoRow}>
                  <span className={styles.infoLbl}>Vendor</span>
                  <span className={styles.infoVal}>{routerInfo?.vendor || 'Analyzing...'}</span>
                </div>
                <div className={styles.infoRow}>
                  <span className={styles.infoLbl}>Capabilities</span>
                  <div className={styles.infoVal} style={{ textAlign: 'right', fontSize: 9 }}>
                    {(routerInfo?.capabilities || ['NAT', 'DHCP']).slice(0, 3).map(c => (
                      <Tag key={c} variant={c.includes('UPnP') ? 'red' : 'mint'}>{c}</Tag>
                    ))}
                  </div>
                </div>
                <div style={{ marginTop: 10 }}>
                  <button 
                    className={styles.ackBtn} 
                    style={{ width: '100%', fontSize: 10 }}
                    onClick={() => window.open(`http://${status.networks[0].gateway}`, '_blank')}
                  >
                    OPEN ADMIN CONSOLE
                  </button>
                </div>
              </>
            )}
          </div>
        </Panel>
      </div>
    </div>
  )
}
