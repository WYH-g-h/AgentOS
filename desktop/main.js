// D:\python学习\AgentOS\desktop\main.js
const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron')
const path = require('path')
const fs = require('fs')
const ProcessManager = require('./processManager')

// ============================================================
// 配置
// ============================================================

const isDev = process.env.NODE_ENV === 'development'
const isWindows = process.platform === 'win32'

// 用户数据目录
const userDataPath = app.getPath('userData')
const agentOSDir = path.join(userDataPath, 'AgentOS')

console.log('📁 用户数据目录:', agentOSDir)

let mainWindow = null
const processManager = new ProcessManager()

// 确保目录存在
function ensureDirectories() {
  const dirs = ['skills', 'workflows', 'data', 'output', 'config', 'logs']
  for (const dir of dirs) {
    const fullPath = path.join(agentOSDir, dir)
    if (!fs.existsSync(fullPath)) {
      fs.mkdirSync(fullPath, { recursive: true })
    }
  }
}
ensureDirectories()

// 获取项目根目录
function getProjectRoot() {
  if (isDev) {
    return path.resolve(__dirname, '..')
  }
  return process.resourcesPath
}

// 获取 app.py 路径
function getAppPath() {
  return path.join(getProjectRoot(), 'api', 'app.py')
}

// ============================================================
// 创建窗口
// ============================================================

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    title: 'AgentOS',
    show: false,
    icon: path.join(__dirname, 'assets', 'icon.png'),
  })

  // ✅ 兼容多种打包方式的前端路径
  const possiblePaths = [
    // 方式1：方法一自动打包 (--extra-resource="../web/dist")
    path.join(process.resourcesPath, 'web', 'dist', 'index.html'),
    // 方式2：手动复制到 app/web/dist
    path.join(process.resourcesPath, 'app', 'web', 'dist', 'index.html'),
    // 方式3：开发模式
    path.join(__dirname, '..', 'web', 'dist', 'index.html'),
  ]

  console.log('📄 资源路径:', process.resourcesPath)

  let loadPath = null
  for (const p of possiblePaths) {
    console.log('📄 检查路径:', p)
    if (fs.existsSync(p)) {
      loadPath = p
      console.log('✅ 找到文件:', p)
      break
    }
  }

  if (loadPath) {
    console.log('📄 最终加载:', loadPath)
    mainWindow.loadFile(loadPath)
  } else {
    console.error('❌ 找不到任何前端文件')
    const errorHtml = `
      <html>
        <head><title>AgentOS 启动失败</title></head>
        <body style="font-family: sans-serif;padding:40px;text-align:center;">
          <h1>❌ 启动失败</h1>
          <p>找不到前端文件</p>
          <p style="font-size:12px;color:#666;text-align:left;margin:20px auto;max-width:600px;background:#f5f5f5;padding:10px;border-radius:4px;">
            尝试过的路径:<br>
            ${possiblePaths.map(p => '  - ' + p + (fs.existsSync(p) ? ' ✅' : ' ❌')).join('<br>')}
          </p>
          <p style="font-size:12px;color:#666;">resources 目录内容:</p>
          <p style="font-size:11px;color:#999;">请确保前端文件已正确构建并复制到 resources/web/dist/ 或 resources/app/web/dist/</p>
        </body>
      </html>
    `
    mainWindow.loadURL(`data:text/html,${encodeURIComponent(errorHtml)}`)
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

// ============================================================
// 应用生命周期
// ============================================================

app.whenReady().then(async () => {
  console.log('='.repeat(50))
  console.log('🚀 AgentOS Desktop 启动中...')
  console.log('='.repeat(50))

  try {
    const appPath = getAppPath()

    // 启动 Python 后端
    await processManager.start(getProjectRoot(), appPath, agentOSDir)
    console.log('✅ Python 后端已启动')

    // 等待后端就绪
    const ready = await processManager.waitForReady()
    if (!ready) {
      console.error('❌ 后端未就绪')
      dialog.showErrorBox('启动失败', '后端服务未就绪，请检查 Python 环境')
      app.quit()
      return
    }
    console.log('✅ 后端已就绪')

    // 创建窗口
    createWindow()
    console.log('✅ 窗口已创建')

    console.log('='.repeat(50))
    console.log('✅ AgentOS 已就绪')
    console.log('='.repeat(50))

  } catch (error) {
    console.error('❌ 启动失败:', error.message)
    dialog.showErrorBox('启动失败', `启动失败:\n\n${error.message}`)
    app.quit()
  }
})

// 所有窗口关闭时 - 关闭后端
app.on('window-all-closed', async () => {
  await processManager.stop()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// 应用激活时（macOS）
app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})

// 应用退出前 - 确保进程被清理
app.on('before-quit', async (event) => {
  event.preventDefault()
  await processManager.stop()
  app.exit()
})

// ============================================================
// IPC 通信
// ============================================================

ipcMain.handle('get-app-info', () => {
  return {
    version: app.getVersion(),
    userDataPath: agentOSDir,
    isDev: isDev,
    platform: process.platform,
  }
})

ipcMain.handle('open-directory', (event, dir) => {
  // ✅ 优先使用 resources 目录
  const baseDir = process.resourcesPath
  const fullPath = path.join(baseDir, dir)

  // 如果 resources 目录不存在，回退到 AppData
  if (!fs.existsSync(fullPath)) {
    const appDataPath = path.join(app.getPath('userData'), 'AgentOS', dir)
    if (fs.existsSync(appDataPath)) {
      shell.openPath(appDataPath)
      return appDataPath
    }
    // 都不存在，创建 resources 目录
    fs.mkdirSync(fullPath, { recursive: true })
  }

  shell.openPath(fullPath)
  return fullPath
})

ipcMain.handle('open-custom-directory', (event, dirPath) => {
  if (fs.existsSync(dirPath)) {
    shell.openPath(dirPath)
  }
  return dirPath
})

ipcMain.handle('get-backend-status', () => {
  return processManager.getStatus()
})