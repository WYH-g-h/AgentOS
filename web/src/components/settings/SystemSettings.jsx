// web/src/components/settings/SystemSettings.jsx
import React, { useState } from 'react'
import { AgentAPI } from '../../services/api'

function SystemSettings({ onReload }) {
  const [reloading, setReloading] = useState(false)

  const handleReload = async () => {
    setReloading(true)
    try {
      const resp = await AgentAPI.adminReload()
      alert(resp.data?.message || '✅ 热加载完成')
      // ✅ 通知父组件刷新数据，而不是刷新整个页面
      if (onReload) {
        console.log('🔄 热加载完成，刷新数据')
        onReload()
      }
    } catch (e) {
      alert('热加载失败: ' + e.message)
    } finally {
      setReloading(false)
    }
  }

  return (
    <div className="system-settings">
      <h3>⚙️ 系统设置</h3>

      <div className="model-section">
        <h4>🔄 热加载</h4>
        <p style={{ color: '#6c757d', fontSize: 14, marginBottom: 12 }}>
          重新加载技能和工作流，无需重启应用
        </p>
        <button
          className="btn-primary"
          onClick={handleReload}
          disabled={reloading}
        >
          {reloading ? '⏳ 加载中...' : '🔄 重新加载技能和工作流'}
        </button>
      </div>

      <div className="model-section" style={{ marginTop: 24 }}>
        <h4>📊 系统信息</h4>
        <div style={{ background: '#f8f9fa', padding: 16, borderRadius: 8 }}>
          <p><strong>版本:</strong> v17.0.0</p>
          <p><strong>平台:</strong> {navigator.platform}</p>
          <p><strong>运行环境:</strong> {window.electronAPI ? 'Electron' : 'Web'}</p>
        </div>
      </div>

      <div className="model-section" style={{ marginTop: 24 }}>
        <h4>💡 使用提示</h4>
        <ul style={{ color: '#495057', lineHeight: 1.8, paddingLeft: 20 }}>
          <li>技能和工作流存储在 resources/ 目录下的 YAML 文件中</li>
          <li>修改后点击"重新加载"即可生效</li>
          <li>数据目录和输出目录可以自定义路径</li>
          <li>云模型 API Key 仅保存在本地配置文件</li>
        </ul>
      </div>
    </div>
  )
}

export default SystemSettings