const { app, BrowserWindow, ipcMain, nativeTheme, shell } = require('electron')
const path = require('path')

// Force software rendering - essential for stability in many VM/Crostini environments
app.disableHardwareAcceleration()

// Essential compatibility switches for Linux/Crostini stability
app.commandLine.appendSwitch('no-sandbox')
app.commandLine.appendSwitch('disable-setuid-sandbox')
app.commandLine.appendSwitch('disable-gpu-sandbox')
app.commandLine.appendSwitch('disable-dev-shm-usage') 
app.commandLine.appendSwitch('disable-gpu') // Force software rendering for stability in VMs
app.commandLine.appendSwitch('ozone-platform', 'x11')
app.commandLine.appendSwitch('disable-http-cache') // Prevent stale data issues

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "Mint NetScout SIGINT PRO",
    backgroundColor: '#0a0f14', 
    show: false, // Don't show until ready-to-show
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  win.once('ready-to-show', () => {
    win.show()
  })

  // ── IPC Handlers ───────────────────────────────────────────────────────────
  ipcMain.on('open-external', (event, url) => {
    if (url.startsWith('http')) {
      console.log(`[IPC-OPEN] ${url}`)
      shell.openExternal(url).catch(err => console.error(`[IPC-ERR] ${err}`))
    }
  })

  // ── Navigation & Link Interception ─────────────────────────────────────────
  
  // 1. Prevent the main window from navigating away from the dashboard
  win.webContents.on('will-navigate', (event, url) => {
    const isLocal = url.startsWith('http://127.0.0.1:5000') || url.startsWith('http://localhost:5000')
    if (!isLocal) {
      event.preventDefault()
      console.log(`[NAV-BLOCK] Blocked internal jump to: ${url}`)
      shell.openExternal(url).catch(err => console.error(`[NAV-ERR] ${err}`))
    }
  })

  // 2. Handle window.open and <a target="_blank">
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) {
      console.log(`[POPUP-BLOCK] Opening external: ${url}`)
      shell.openExternal(url).catch(err => console.error(`[POPUP-ERR] ${err}`))
      return { action: 'deny' } // Stop Electron from opening a blank window
    }
    return { action: 'allow' }
  })

  // ── Logging & Errors ───────────────────────────────────────────────────────
  
  // Bulletproof log capture
  win.webContents.on('console-message', (event, level, message) => {
    const msg = (typeof level === 'object' && level !== null) ? level.message : message
    if (msg) console.log(`[RENDERER] ${msg}`)
  })

  win.webContents.on('did-fail-load', (event, code, desc, url) => {
    if (url.includes('favicon')) return
    console.error(`[FAIL-LOAD] ${url}: ${desc} (${code})`)
  })

  win.webContents.on('render-process-gone', (event, details) => {
    console.error(`[CRASH] Renderer: ${details.reason} (${details.exitCode})`)
  })

  // ── Load Backend ───────────────────────────────────────────────────────────
  const loadURL = () => {
    win.loadURL('http://127.0.0.1:5000').catch(err => {
      console.log(`[RETRY] Backend not ready (Error: ${err.code}), waiting...`)
      setTimeout(loadURL, 2000)
    })
  }

  loadURL()
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
