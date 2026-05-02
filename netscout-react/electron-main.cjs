const { app, BrowserWindow, ipcMain, nativeTheme } = require('electron')
const path = require('path')

// Essential compatibility switches for Linux/Crostini stability
// The 'dangling raw_ptr' crash is a known Chromium issue on some Linux envs with sandbox
app.commandLine.appendSwitch('no-sandbox')
app.commandLine.appendSwitch('disable-setuid-sandbox')
app.commandLine.appendSwitch('disable-gpu-sandbox')
app.commandLine.appendSwitch('ozone-platform', 'x11')

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "Mint NetScout SIGINT PRO",
    backgroundColor: '#0a0f14', 
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false, // Disabled for Linux/Crostini stability
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  // Capture ALL logs to stdout - robust handler for different Electron versions
  win.webContents.on('console-message', (event, ...args) => {
    // args[0] is level, args[1] is message in older versions
    // in newer versions, args[0] is the details object
    const details = args[0]
    const message = (typeof details === 'object' && details !== null) ? details.message : args[1]
    if (message) console.log(`[RENDERER] ${message}`)
  })

  win.webContents.on('render-process-gone', (event, details) => {
    console.error(`[CRASH] Renderer: ${details.reason} (${details.exitCode})`)
  })

  // Load backend with retry
  const loadURL = () => {
    win.loadURL('http://localhost:5000').catch(err => {
      console.log('[RETRY] Backend not ready, waiting...')
      setTimeout(loadURL, 2000)
    })
  }

  loadURL()
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
