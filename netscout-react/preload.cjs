const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  toggleDarkMode: (isDark) => ipcRenderer.send('dark-mode:toggle', isDark),
  openExternal: (url) => ipcRenderer.send('open-external', url)
})
