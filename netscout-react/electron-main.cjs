const { app, BrowserWindow, ipcMain, nativeTheme } = require('electron')
const path = require('path')
const http = require('http')

// ULTIMATE STABILITY: Forced Software Rendering for Chromebook/Crostini
app.disableHardwareAcceleration()

// Force X11 and disable all possible GPU/DRM/Sandbox probes
app.commandLine.appendSwitch('ozone-platform', 'x11')
app.commandLine.appendSwitch('ozone-platform-hint', 'x11')
app.commandLine.appendSwitch('disable-gpu')
app.commandLine.appendSwitch('no-sandbox')
app.commandLine.appendSwitch('disable-gpu-sandbox')
// app.commandLine.appendSwitch('disable-software-rasterizer') // REMOVED: We NEED software rasterizer if GPU is off
app.commandLine.appendSwitch('disable-dev-shm-usage')
app.commandLine.appendSwitch('disable-gpu-compositing')
app.commandLine.appendSwitch('disable-vulkan')
app.commandLine.appendSwitch('disable-accelerated-2d-canvas')
app.commandLine.appendSwitch('disable-gpu-rasterization')
app.commandLine.appendSwitch('in-process-gpu')
app.commandLine.appendSwitch('no-zygote')
app.commandLine.appendSwitch('disable-setuid-sandbox')
app.commandLine.appendSwitch('disable-namespace-sandbox')
app.commandLine.appendSwitch('disable-features', 'VizDisplayCompositor,WaylandWindowDecorations,WaylandFractionalScaleV1')

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "Mint NetScout SIGINT PRO",
    autoHideMenuBar: true,
    backgroundColor: '#0a0f14', 
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
      spellcheck: false,
      backgroundThrottling: false,
    },
    icon: path.join(__dirname, 'public', 'favicon.svg')
  })

  // Theme Sync Handler
  ipcMain.on('dark-mode:toggle', (event, mode) => {
    nativeTheme.themeSource = mode ? 'dark' : 'light'
    return nativeTheme.shouldUseDarkColors
  })

  win.on('closed', () => {
    app.quit()
  })

  // Handle load failures
  win.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error(`[!] Page failed to load: ${errorCode} (${errorDescription})`)
    if (errorCode === -102 || errorCode === -105) { // Connection refused or DNS failed
      console.log('[*] Retrying in 2s...')
      setTimeout(() => win.loadURL('http://localhost:5000'), 2000)
    }
  })

  // Auto-open DevTools if requested via ENV or to help debugging
  if (process.env.NETSCOUT_DEBUG === '1') {
    win.webContents.openDevTools({ mode: 'detach' })
  }

  // Load the local Flask server
  win.loadURL('http://localhost:5000')
}

app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})


app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
