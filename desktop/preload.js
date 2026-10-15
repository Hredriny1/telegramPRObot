const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  saveSettings: (s) => ipcRenderer.invoke('save-settings', s),
  getSettings: () => ipcRenderer.invoke('get-settings'),
  sendCommand: (cmd) => ipcRenderer.invoke('send-command', cmd)
});
