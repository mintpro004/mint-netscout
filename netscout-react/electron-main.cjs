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

  // IPC handler to open external URLs securely
  ipcMain.on('open-external', (event, url) => {
    if (url.startsWith('http')) {
      console.log(`[IPC] Opening external URL: ${url}`)
      shell.openExternal(url)
    }
  })

  // 🛡️ SECURITY: Prevent the main window from navigating away from the dashboard
  win.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith('http://127.0.0.1:5000') && !url.startsWith('http://localhost:5000')) {
      event.preventDefault()
      shell.openExternal(url)
    }
  })

  // Handle new window requests (like the Admin Console button)
  win.webContents.setWindowOpenHandler(({ url }) => {
    // Open ANY external URL in the user's default browser
    if (url.startsWith('http')) {
      console.log(`[EXTERNAL] Opening URL in system browser: ${url}`)
      shell.openExternal(url)
      return { action: 'deny' }
    }
    return { action: 'allow' }
  })

  // Capture ALL logs to stdout
  win.webContents.on('console-message', (event, ...args) => {
    const details = args[0]
    const message = (typeof details === 'object' && details !== null) ? details.message : args[1]
    if (message) console.log(`[RENDERER] ${message}`)
  })

  win.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    console.error(`[ERROR] Failed to load ${validatedURL}: ${errorDescription} (${errorCode})`)
  })

  win.webContents.on('render-process-gone', (event, details) => {
    console.error(`[CRASH] Renderer: ${details.reason} (${details.exitCode})`)
  })

  // Load backend with retry - Use 127.0.0.1
  const loadURL = () => {
    win.loadURL('http://127.0.0.1:5000').catch(err => {
      console.log(`[RETRY] Backend not ready, waiting...`)
      setTimeout(loadURL, 2000)
    })
  }

  loadURL()
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
