// desktop/cleanup.js
/**
 * 清理脚本 - 用于手动清理残留进程
 * 运行: npm run clean
 */
const { exec } = require('child_process')
const util = require('util')

const execPromise = util.promisify(exec)

async function cleanup() {
  console.log('🧹 清理 AgentOS 相关进程...')
  console.log('='.repeat(40))

  try {
    console.log('  清理 Python 进程...')
    try {
      const result = await execPromise('taskkill /F /IM python.exe 2>nul')
      if (result.stdout && result.stdout.trim()) {
        console.log(`    ${result.stdout.trim()}`)
      }
    } catch (e) {
      console.log('    没有 Python 进程在运行')
    }

    try {
      const result = await execPromise('taskkill /F /IM pythonw.exe 2>nul')
      if (result.stdout && result.stdout.trim()) {
        console.log(`    ${result.stdout.trim()}`)
      }
    } catch (e) {
      // 没有找到进程是正常的
    }

    console.log('  清理 AgentOS 进程...')
    try {
      const result = await execPromise('taskkill /F /IM AgentOS.exe 2>nul')
      if (result.stdout && result.stdout.trim()) {
        console.log(`    ${result.stdout.trim()}`)
      }
    } catch (e) {
      console.log('    没有 AgentOS 进程在运行')
    }

    console.log('='.repeat(40))
    console.log('✅ 清理完成！')

  } catch (error) {
    console.error('❌ 清理失败:', error.message)
  }
}

cleanup()

setTimeout(() => {
  process.exit(0)
}, 3000)