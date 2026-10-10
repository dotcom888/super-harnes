const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  selectDirectory: () => ipcRenderer.invoke('dialog:select-directory'),
  openExternal: (url) => ipcRenderer.send('shell:open-external', url),
  backendUrl: 'http://127.0.0.1:8765',
  wsUrl: 'ws://127.0.0.1:8765/ws',

  // 终端会话操作
  terminalCreate: (params) => ipcRenderer.invoke('terminal:create', params),
  terminalWrite: (params) => ipcRenderer.send('terminal:write', params),
  terminalKill: (params) => ipcRenderer.send('terminal:kill', params),
  onTerminalData: (id, callback) => {
    const channel = `terminal:data:${id}`;
    const listener = (_event, data) => callback(data);
    ipcRenderer.on(channel, listener);
    return () => ipcRenderer.removeListener(channel, listener);
  },
  onTerminalExit: (id, callback) => {
    const channel = `terminal:exit:${id}`;
    const listener = (_event, code) => callback(code);
    ipcRenderer.on(channel, listener);
    return () => ipcRenderer.removeListener(channel, listener);
  }
});
