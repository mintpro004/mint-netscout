const { app, BrowserWindow, ipcMain, nativeTheme } = require('electron')
const path = require('path')

// DO NOT disable hardware acceleration yet — let Electron decide
// app.disableHardwareAcceleration() 

// Essential compatibility switches (Removed no-sandbox per user request)
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
      sandbox: true, // Enabled sandbox
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  // Capture ALL logs to stdout
  win.webContents.on('console-message', (event, details) => {
    console.log(`[RENDERER] ${details.message}`)
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
