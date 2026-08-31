// desktop/processManager.js
/**
 * 进程管理器 - 负责 Python 后端的启动、监控和清理
 */
const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')
const http = require('http')

class ProcessManager {
  constructor() {
    this.pythonProcess = null
    this.backendReady = false
    this.isShuttingDown = false
    this.startupTimeout = 30000
    this.maxRetries = 3
    this.retryCount = 0
  }

  /**
   * 获取 Python 路径
   */
  getPythonPath(projectRoot) {
    const embeddedPython = path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
    if (fs.existsSync(embeddedPython)) {
      return embeddedPython
    }
    return 'python'
  }

  /**
   * 启动 Python 后端
   */
  async start(projectRoot, appPath, agentOSDir, envVars = {}) {
    if (this.pythonProcess && !this.pythonProcess.killed) {
      console.log('⚠️ Python 后端已在运行')
      return true
    }

    this.isShuttingDown = false
    const pythonPath = this.getPythonPath(projectRoot)

    if (!fs.existsSync(appPath)) {
      throw new Error(`找不到 app.py: ${appPath}`)
    }

    console.log('🚀 启动 Python 后端...')
    console.log('  Python:', pythonPath)
    console.log('  App:', appPath)

    return new Promise((resolve, reject) => {
      const env = {
        ...process.env,
        PYTHONPATH: projectRoot,
        AGENTOS_DATA_DIR: agentOSDir,
        AGENTOS_ENV: 'desktop',
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1',
        ...envVars,
      }

      this.pythonProcess = spawn(pythonPath, [appPath], {
        env: env,
        stdio: ['ignore', 'pipe', 'pipe'],
        detached: false,
        cwd: projectRoot,
        windowsHide: true,
      })

      let resolved = false

      this.pythonProcess.stdout.on('data', (data) => {
        const output = data.toString('utf-8')
        console.log('[Python]', output.trim())

        if (!resolved && (output.includes('Application startup complete') ||
            output.includes('✅ AgentOS API Server 就绪'))) {
          resolved = true
          this.backendReady = true
          this.retryCount = 0
          resolve(true)
        }
      })

      this.pythonProcess.stderr.on('data', (data) => {
        const output = data.toString('utf-8')
        console.error('[Python Error]', output.trim())
      })

      this.pythonProcess.on('close', (code) => {
        console.log(`Python 进程退出，代码: ${code}`)
        this.backendReady = false

        if (!this.isShuttingDown && code !== 0 && code !== null && !resolved) {
          if (this.retryCount < this.maxRetries) {
            this.retryCount++
            console.log(`🔄 重试启动 (${this.retryCount}/${this.maxRetries})...`)
            setTimeout(() => {
              this.start(projectRoot, appPath, agentOSDir, envVars)
                .then(resolve)
                .catch(reject)
            }, 2000 * this.retryCount)
          } else {
            reject(new Error(`Python 进程异常退出，代码: ${code}`))
          }
        }
      })

      this.pythonProcess.on('error', (err) => {
        if (!resolved) {
          reject(new Error(`启动 Python 失败: ${err.message}`))
        }
      })

      setTimeout(() => {
        if (!resolved && !this.backendReady) {
          reject(new Error('Python 后端启动超时 (30秒)'))
        }
      }, this.startupTimeout)
    })
  }

  /**
   * 停止 Python 后端
   */
  async stop() {
    this.isShuttingDown = true

    if (this.pythonProcess) {
      console.log('🛑 停止 Python 后端...')

      // 1. 先尝试优雅关闭
      try {
        this.pythonProcess.kill('SIGTERM')
      } catch (e) {
        // 忽略
      }

      // 2. 等待进程结束
      await new Promise((resolve) => {
        let attempts = 0
        const maxAttempts = 20

        const checkProcess = () => {
          attempts++
          if (this.pythonProcess.killed || attempts >= maxAttempts) {
            // 强制结束
            try {
              if (!this.pythonProcess.killed) {
                this.pythonProcess.kill('SIGKILL')
              }
            } catch (e) {
              // 忽略
            }
            resolve()
          } else {
            setTimeout(checkProcess, 200)
          }
        }

        checkProcess()
      })

      this.pythonProcess = null
      this.backendReady = false
    }

    // 3. 清理残留进程
    await this.cleanupResidualProcesses()

    console.log('✅ Python 后端已停止')
  }

  /**
   * 清理残留的 Python 进程
   */
  async cleanupResidualProcesses() {
    try {
      const { exec } = require('child_process')

      if (process.platform === 'win32') {
        exec('taskkill /F /IM python.exe 2>nul', (error, stdout) => {
          if (stdout && stdout.trim()) {
            console.log('[Cleanup]', stdout.trim())
          }
        })
        exec('taskkill /F /IM pythonw.exe 2>nul', (error, stdout) => {
          if (stdout && stdout.trim()) {
            console.log('[Cleanup]', stdout.trim())
          }
        })
      }
    } catch (e) {
      // 忽略错误
    }
  }

  /**
   * 检查后端是否运行
   */
  async checkHealth(port = 8000) {
    return new Promise((resolve) => {
      const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
        resolve(res.statusCode === 200)
      })
      req.on('error', () => resolve(false))
      req.setTimeout(2000, () => resolve(false))
    })
  }

  /**
   * 等待后端就绪
   */
  async waitForReady(maxAttempts = 30, port = 8000) {
    for (let i = 0; i < maxAttempts; i++) {
      const ready = await this.checkHealth(port)
      if (ready) {
        this.backendReady = true
        return true
      }
      await new Promise(resolve => setTimeout(resolve, 500))
    }
    return false
  }

  /**
   * 获取进程状态
   */
  getStatus() {
    return {
      running: this.pythonProcess !== null && !this.pythonProcess.killed,
      ready: this.backendReady,
      pid: this.pythonProcess ? this.pythonProcess.pid : null,
      isShuttingDown: this.isShuttingDown,
    }
  }
}

module.exports = ProcessManager