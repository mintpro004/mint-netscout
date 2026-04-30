import { useState } from 'react'
import { useNetScout }   from './hooks/useNetScout'
import { toast }          from './hooks/useToast'
import { ToastLayer }     from './components/ui'
import Sidebar            from './components/Sidebar'
import Topbar             from './components/Topbar'
import ScanBanner         from './components/ScanBanner'
import DeviceModal        from './components/DeviceModal'
import { AddDeviceModal, UpdateModal, ExitModal } from './components/Modals'
import Dashboard          from './pages/Dashboard'
import Devices            from './pages/Devices'
import { Threats, Alerts, Network, Settings } from './pages/Pages'
import styles             from './App.module.css'

export default function App() {
  const ns = useNetScout()
  const {
    devices, visible, hidden, online, trusted, unsafe, alerts, unacked,
    status, scanning, scanMsg, connected, hiddenMacs,
    triggerScan, blockDevice, removeDevice,
    investigateDevice, ackAlert, hideDevice, clearHidden,
    checkUpdates, addDevice, fetchAll,
  } = ns

  const [view,        setView]        = useState('dashboard')
  const [selectedMac, setSelectedMac] = useState(null)
  const [showAdd,     setShowAdd]     = useState(false)
  const [showExit,    setShowExit]    = useState(false)
  const [updateInfo,  setUpdateInfo]  = useState(null)
  const [updLoading,  setUpdLoading]  = useState(false)
  const [settings,    setSettings]    = useState({ animations: true, stealth: true, interval: '30' })

  const handleBlock = async (mac, blocked) => {
    const res = await blockDevice(mac, blocked)
    if (res?.success) toast(blocked ? '🚫 Device BLOCKED' : '🔓 Device UNBLOCKED', blocked ? 'error' : 'success')
    else toast.error('Block action failed')
    return res
  }

  const handleRemove = async (mac) => {
    const res = await removeDevice(mac)
    if (res?.success) { toast.info('Device removed from registry'); setSelectedMac(null) }
    else toast.error('Remove failed')
    return res
  }

  const handleInvestigate = async (mac) => {
    const res = await investigateDevice(mac)
    if (res?.success) toast.success(`Investigation complete — ${(res.ports || []).length} port(s) found`)
    else if (res !== null) toast.error('Investigation failed')
    return res
  }

  const handleCheckUpdates = async () => {
    setUpdLoading(true)
    toast.info('Contacting update server…')
    const info = await checkUpdates()
    setUpdLoading(false)
    if (info) setUpdateInfo(info)
    else toast.error('Update check failed')
  }

  const handleApplyUpdate = () => {
    setUpdateInfo(null)
    setUpdLoading(false)
    toast.info('Downloading update…')
    setTimeout(() => { toast.success('Update applied — restart to activate'); fetchAll() }, 3000)
  }

  const handleScan = (aggressive) => {
    triggerScan(aggressive)
    toast.info(aggressive ? 'Aggressive scan initiated…' : 'Deep scan initiated…')
  }

  const handleExit = () => {
    window.close()
    setTimeout(() => {
      document.body.innerHTML = '<div style="color:#00ffaa;font-family:monospace;padding:40px;background:#020408;height:100vh;display:grid;place-items:center;font-size:18px;letter-spacing:3px">[ NETSCOUT SESSION TERMINATED ]</div>'
    }, 100)
  }

  return (
    <>
      <ToastLayer />
      {selectedMac && (
        <DeviceModal
          mac={selectedMac}
          devices={devices}
          onClose={() => setSelectedMac(null)}
          onInvestigate={handleInvestigate}
          onBlock={handleBlock}
          onRemove={handleRemove}
          onHide={hideDevice}
        />
      )}
      {showAdd    && <AddDeviceModal onClose={() => setShowAdd(false)} onAdd={addDevice} />}
      {updateInfo && <UpdateModal info={updateInfo} onClose={() => setUpdateInfo(null)} onApply={handleApplyUpdate} />}
      {showExit   && <ExitModal onClose={() => setShowExit(false)} onConfirm={handleExit} />}

      <div className={styles.shell}>
        <Sidebar
          view={view} setView={setView}
          connected={connected}
          threatCount={unsafe.length}
          alertCount={unacked.length}
          hiddenCount={hidden.length}
          onAddDevice={() => setShowAdd(true)}
          onCheckUpdates={handleCheckUpdates}
          onClearHidden={clearHidden}
          onExit={() => setShowExit(true)}
          updLoading={updLoading}
        />

        <Topbar
          onlineCount={online.filter(d => !hiddenMacs.has(d.mac)).length}
          totalCount={visible.length}
          trustedCount={trusted.filter(d => !hiddenMacs.has(d.mac)).length}
          threatCount={unsafe.length}
          connected={connected}
          scanning={scanning}
          onScan={handleScan}
        />

        <main className={styles.main}>
          {scanning && <ScanBanner message={scanMsg} />}

          {view === 'dashboard' && (
            <Dashboard
              visible={visible} online={online} trusted={trusted}
              unsafe={unsafe} alerts={alerts} status={status}
              scanning={scanning} hiddenMacs={hiddenMacs}
              onSelectDevice={setSelectedMac} onAck={ackAlert}
            />
          )}
          {view === 'devices' && (
            <Devices
              visible={visible} hidden={hidden} hiddenMacs={hiddenMacs}
              onSelect={setSelectedMac} onRemove={handleRemove} onHide={hideDevice}
            />
          )}
          {view === 'threats' && (
            <Threats unsafe={unsafe} onSelectDevice={setSelectedMac} onBlock={handleBlock} />
          )}
          {view === 'alerts' && (
            <Alerts alerts={alerts} onAck={ackAlert} />
          )}
          {view === 'network' && (
            <Network status={status} />
          )}
          {view === 'settings' && (
            <Settings
              settings={settings} setSettings={setSettings}
              hiddenMacs={hiddenMacs} onClearHidden={clearHidden}
              onCheckUpdates={handleCheckUpdates} onExit={() => setShowExit(true)}
              updLoading={updLoading} connected={connected} devices={devices}
            />
          )}
        </main>
      </div>
    </>
  )
}
