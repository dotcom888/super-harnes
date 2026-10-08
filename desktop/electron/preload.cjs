const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  selectDirectory: () => ipcRenderer.invoke('dialog:select-directory'),
  backendUrl: 'http://127.0.0.1:8765',
  wsUrl: 'ws://127.0.0.1:8765/ws'
});
