const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  toggleDarkMode: (isDark) => ipcRenderer.send('dark-mode:toggle', isDark)
})
