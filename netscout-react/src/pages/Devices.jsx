import { useState, useMemo } from 'react'
import { Panel, PanelHeader, Tag, Badge, Btn, Sdot, Input } from '../components/ui'
import { deviceIcon, fmtMac, fmtAgo } from '../utils'
import styles from './Devices.module.css'

const FILTERS = [
  ['all',        'All'],
  ['online',     '● Online'],
  ['offline',    '○ Offline'],
  ['trusted',    '✓ Trusted'],
  ['unverified', '⚠ Unverified'],
  ['hidden',     '👁 Hidden'],
]

export default function Devices({ visible, hidden, hiddenMacs, onSelect, onRemove, onHide }) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')

  const pool = filter === 'hidden' ? hidden : visible
  const q = search.toLowerCase().trim()

  const filtered = useMemo(() => pool.filter(d => {
    const matchQ = !q
      || (d.ip       || '').includes(q)
      || (d.mac      || '').toLowerCase().includes(q)
      || (d.hostname || '').toLowerCase().includes(q)
      || (d.vendor   || '').toLowerCase().includes(q)
      || (d.alias    || '').toLowerCase().includes(q)
    const matchF =
      filter === 'all'        ||
      filter === 'hidden'     ||
      (filter === 'online'     && d.is_online)   ||
      (filter === 'offline'    && !d.is_online)  ||
      (filter === 'trusted'    && d.is_trusted)  ||
      (filter === 'unverified' && !d.is_trusted)
    return matchQ && matchF
  }), [pool, q, filter])

  return (
    <Panel accent="mint" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <PanelHeader title="Asset Registry">
        <Tag variant="mint">{filtered.length} ASSETS</Tag>
        {hidden.length > 0 && (
          <Tag variant="purple">👁 {hidden.length} HIDDEN</Tag>
        )}
      </PanelHeader>

      <div className={styles.filterBar}>
        <Input
          placeholder="Search IP, MAC, hostname, alias…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ width: 240 }}
        />
        {FILTERS.map(([id, lbl]) => (
          <button
            key={id}
            className={`${styles.filterBtn} ${filter === id ? styles.filterOn : ''} ${id === 'hidden' ? styles.filterHidden : ''}`}
            onClick={() => setFilter(id)}
          >
            {lbl}
          </button>
        ))}
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.tbl}>
          <thead>
            <tr>
              {['', 'Asset', 'IP', 'MAC', 'Trust', 'Status', 'Last Seen', 'Actions'].map(h => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(d => {
              const isHidden = hiddenMacs.has(d.mac)
              return (
                <tr
                  key={d.mac || d.ip}
                  onClick={() => onSelect(d.mac || d.ip)}  // FIX: pass MAC string
                  style={isHidden ? { opacity: .4 } : {}}
                >
                  <td><span style={{ fontSize: 18 }}>{deviceIcon(d)}</span></td>
                  <td>
                    <div className={styles.devName}>{d.alias || d.hostname || d.ip || 'UNKNOWN'}</div>
                    <div className={styles.devVendor}>{d.vendor || '—'}</div>
                  </td>
                  <td><span className={styles.mono}>{d.ip || '—'}</span></td>
                  <td><span className={styles.mono} style={{ fontSize: 9 }}>{fmtMac(d.mac)}</span></td>
                  <td>
                    <Badge variant={d.is_trusted ? 'trusted' : 'warn'}>
                      {d.is_trusted ? '✓ TRUSTED' : '⚠ UNVERIFIED'}
                    </Badge>
                  </td>
                  <td><Sdot online={d.is_online} /></td>
                  <td><span className={styles.xs}>{fmtAgo(d.last_seen)}</span></td>
                  <td
                    className={styles.actions}
                    onClick={e => e.stopPropagation()}
                  >
                    <Btn
                      variant="red" size="sm"
                      onClick={() => {
                        if (confirm(`Remove ${d.alias || d.hostname || d.ip}?`)) {
                          onRemove(d.mac)
                        }
                      }}
                    >
                      🗑
                    </Btn>
                    <Btn
                      variant="purple" size="sm"
                      onClick={() => onHide(d.mac)}
                    >
                      {isHidden ? 'Show' : 'Hide'}
                    </Btn>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className={styles.empty}>
            {filter === 'hidden' ? 'NO HIDDEN DEVICES' : 'NO ASSETS MATCH FILTER'}
          </div>
        )}
      </div>
    </Panel>
  )
}
