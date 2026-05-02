const { app, BrowserWindow, ipcMain, nativeTheme } = require('electron')
const path = require('path')

// Essential compatibility switches for Linux/Crostini stability
app.commandLine.appendSwitch('no-sandbox')
app.commandLine.appendSwitch('disable-setuid-sandbox')
app.commandLine.appendSwitch('disable-gpu-sandbox')
app.commandLine.appendSwitch('disable-namespace-sandbox')
app.commandLine.appendSwitch('no-zygote')
app.commandLine.appendSwitch('disable-dev-shm-usage') // Fixes /dev/shm permission issues
app.commandLine.appendSwitch('ozone-platform', 'x11')
app.commandLine.appendSwitch('disable-gpu') // Force software rendering for stability in VMs
app.commandLine.appendSwitch('disable-software-rasterizer')
app.commandLine.appendSwitch('disable-accelerated-2d-canvas')

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

  // Load backend with retry - Use 127.0.0.1 to avoid DNS resolution issues
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
