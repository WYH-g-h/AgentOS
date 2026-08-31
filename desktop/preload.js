// D:\python学习\AgentOS\desktop\preload.js
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: true,  // ✅ 添加这个标志
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),
  openDirectory: (dir) => ipcRenderer.invoke('open-directory', dir),
  platform: process.platform,
  isDev: process.env.NODE_ENV === 'development',
})

console.log('✅ preload.js 已加载')