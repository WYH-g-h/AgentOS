// web/src/components/settings/ToolManager.jsx
import React, { useState, useEffect } from 'react'
import { AgentAPI } from '../../services/api'

// ✅ 工具模板（前端硬编码）
const TOOL_TEMPLATE = `# tools/my_tool.py
\"\"\"
工具名称: my_tool
描述: 这是我的工具描述
\"\"\"

from tools.registry import tool_registry


def my_function(param1: str = "default") -> str:
    \"\"\"
    工具实现函数

    Args:
        param1: 参数说明

    Returns:
        str: 返回结果说明
    \"\"\"
    # 在这里实现你的工具逻辑
    result = f"处理完成: {param1}"
    return result


def register(registry):
    \"\"\"注册工具到注册表（必须实现）\"\"\"
    registry.register_tool(
        name="my_tool",
        func=my_function,
        description="我的工具描述"
    )
`

function ToolManager() {
  const [tools, setTools] = useState([])
  const [customTools, setCustomTools] = useState([])
  const [loading, setLoading] = useState(true)
  const [reloading, setReloading] = useState(false)
  const [showTemplate, setShowTemplate] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [toolsResp, customResp] = await Promise.all([
        AgentAPI.adminListTools(),
        AgentAPI.adminListCustomTools(),
      ])
      setTools(toolsResp.data?.tools || [])
      setCustomTools(customResp.data?.tools || [])
    } catch (e) {
      console.error('加载工具失败:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleReload = async () => {
    setReloading(true)
    try {
      const resp = await AgentAPI.adminReloadTools()
      alert(resp.data?.message || '✅ 工具热加载完成')
      loadData()
    } catch (e) {
      alert('热加载失败: ' + e.message)
    } finally {
      setReloading(false)
    }
  }

  const handleClear = async () => {
    if (!confirm('确定清空所有自定义工具吗？')) return
    try {
      const resp = await AgentAPI.adminClearTools()
      alert(resp.data?.message || '✅ 已清空')
      loadData()
    } catch (e) {
      alert('清空失败: ' + e.message)
    }
  }

  if (loading) return <div className="loading">加载中...</div>

  return (
    <div className="tool-manager">
      <div className="manager-header">
        <h3>🔧 工具管理 ({tools.length})</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn-primary"
            onClick={handleReload}
            disabled={reloading}
          >
            {reloading ? '⏳ 加载中...' : '🔄 热加载'}
          </button>
          <button className="btn-danger" onClick={handleClear}>
            🗑️ 清空自定义
          </button>
          <button className="btn-secondary" onClick={() => setShowTemplate(!showTemplate)}>
            📄 模板
          </button>
        </div>
      </div>

      {showTemplate && (
        <div className="template-panel">
          <div className="template-header">
            <span>📄 工具模板</span>
            <button className="modal-close" onClick={() => setShowTemplate(false)}>✕</button>
          </div>
          <div className="template-body">
            <div className="hint">
              💡 在 <code>tools/</code> 目录下创建 <code>.py</code> 文件，实现 <code>register(registry)</code> 函数即可添加自定义工具
            </div>
            <pre className="template-code">{TOOL_TEMPLATE}</pre>
          </div>
        </div>
      )}

      <div className="model-section">
        <h4>📦 内置工具 ({tools.filter(t => t.is_builtin).length})</h4>
        <div className="tool-grid">
          {tools.filter(t => t.is_builtin).map(tool => (
            <div key={tool.name} className="tool-card builtin">
              <div className="tool-name">🔧 {tool.display_name || tool.name}</div>
              <div className="tool-desc">{tool.description}</div>
              <div className="tool-id">{tool.name}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="model-section">
        <h4>🧩 自定义工具 ({customTools.length})</h4>
        {customTools.length === 0 ? (
          <div className="empty-state">暂无自定义工具</div>
        ) : (
          <div className="tool-grid">
            {customTools.map(tool => (
              <div key={tool.name} className="tool-card custom">
                <div className="tool-name">🧩 {tool.name}</div>
                <div className="tool-desc">{tool.file}</div>
                <div className="tool-path">{tool.path}</div>
              </div>
            ))}
          </div>
        )}
        <div className="hint" style={{ marginTop: 12, fontSize: 12, color: '#6c757d' }}>
          💡 点击 <strong>"模板"</strong> 查看工具创建示例
        </div>
      </div>
    </div>
  )
}

export default ToolManager