const { app, BrowserWindow, ipcMain, nativeTheme } = require('electron')
const path = require('path')

// ULTRA STABILITY: Forced Software Rendering for Chromebook/Crostini
app.commandLine.appendSwitch('disable-gpu')
app.commandLine.appendSwitch('no-sandbox')
app.commandLine.appendSwitch('disable-software-rasterizer')
app.commandLine.appendSwitch('disable-dev-shm-usage')
app.commandLine.appendSwitch('disable-gpu-compositing')
app.commandLine.appendSwitch('disable-vulkan')
app.commandLine.appendSwitch('disable-accelerated-2d-canvas')
app.commandLine.appendSwitch('disable-gpu-rasterization')
app.commandLine.appendSwitch('in-process-gpu')
app.commandLine.appendSwitch('ozone-platform', 'x11')
app.commandLine.appendSwitch('no-zygote')
app.commandLine.appendSwitch('disable-setuid-sandbox')
app.commandLine.appendSwitch('disable-namespace-sandbox')
app.commandLine.appendSwitch('disable-features', 'VizDisplayCompositor')

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "Mint NetScout SIGINT PRO",
    autoHideMenuBar: true,
    backgroundColor: '#0a0f14', // Default Dark
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      spellcheck: false,
      backgroundThrottling: false, // Prevent freezing when unfocused
    },
    icon: path.join(__dirname, 'public', 'favicon.svg')
  })

  // Load the local Flask server
  win.loadURL('http://localhost:5000')

  // Theme Sync
  ipcMain.handle('dark-mode:toggle', () => {
    if (nativeTheme.shouldUseDarkColors) {
      nativeTheme.themeSource = 'light'
    } else {
      nativeTheme.themeSource = 'dark'
    }
    return nativeTheme.shouldUseDarkColors
  })

  ipcMain.handle('dark-mode:system', () => {
    nativeTheme.themeSource = 'system'
  })

  win.on('closed', () => {
    app.quit()
  })
}

// Optimization: Single Instance Lock
if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.whenReady().then(() => {
    createWindow()
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
  })
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
