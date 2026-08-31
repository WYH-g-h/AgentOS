// web/src/App.jsx
import React, { useState, useEffect, useCallback } from 'react'
import TopBar from './components/TopBar'
import Sidebar from './components/Sidebar'
import RightPanel from './components/RightPanel'
import Chat from './components/Chat'
import SettingsPage from './components/SettingsPage'
import FileManagerModal from './components/FileManagerModal'
import { useSession } from './hooks/useSession'
import { AgentAPI } from './services/api'
import './App.css'
let lastListLoad = 0
const LIST_CACHE_INTERVAL = 120000 // 120秒内不重新加载

function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showFiles, setShowFiles] = useState(false)
  const [health, setHealth] = useState(null)
  const [tools, setTools] = useState([])
  const [skills, setSkills] = useState([])
  const [workflows, setWorkflows] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  const {
    sessions,
    currentSessionId,
    loadSessions,
    createSession,
    deleteSession,
    renameSession,
    switchSession,
    setCurrentSessionId,
  } = useSession()

  const loadSystemStatus = async () => {
    try {
      console.log('🔄 开始加载系统状态...')

       // 如果距离上次加载不到60秒，只刷新健康检查
      const now = Date.now()
      if (now - lastListLoad < LIST_CACHE_INTERVAL) {
        const [healthResp] = await Promise.all([
          AgentAPI.health().catch(() => ({ data: null })),
        ])
        setHealth(healthResp.data)
        console.log('⏭️ 列表数据未过期，跳过加载')
        setIsLoading(false)
        return
      }

      const [healthResp, toolsResp, skillsResp, workflowsResp] = await Promise.all([
        AgentAPI.health().catch(() => ({ data: null })),
        AgentAPI.listTools().catch(() => ({ data: [] })),
        AgentAPI.listSkills().catch(() => ({ data: [] })),
        AgentAPI.listWorkflows().catch(() => ({ data: [] })),
      ])

      setHealth(healthResp.data)
      setTools(Array.isArray(toolsResp.data) ? toolsResp.data : [])
      setSkills(Array.isArray(skillsResp.data) ? skillsResp.data : [])
      setWorkflows(Array.isArray(workflowsResp.data) ? workflowsResp.data : [])

    } catch (e) {
      console.error('❌ 加载系统状态失败:', e)
      setTools([])
      setSkills([])
      setWorkflows([])
    } finally {
      setIsLoading(false)
    }
  }

  // 热加载回调 - 刷新数据而不是刷新页面
  const handleReload = () => {
    loadSystemStatus()
    loadSessions()
  }

  useEffect(() => {
    loadSystemStatus()
    const interval = setInterval(loadSystemStatus, 120000)
    return () => clearInterval(interval)
  }, [])

  const handleNewSession = async () => {
    const sid = await createSession()
    if (sid) {
      console.log('🔄 切换到新会话:', sid)
      switchSession(sid)
    }
  }

  const handleSwitchSession = (sid) => {
    console.log('🔄 切换会话:', sid)
    switchSession(sid)
  }

  const handleRenameSession = async (sid, newName) => {
    console.log('📝 App 重命名:', sid, newName)
    await renameSession(sid, newName)
  }

  const handleSessionUpdate = (sid) => {
    if (sid && !currentSessionId) {
      setCurrentSessionId(sid)
    }
    loadSessions()
  }

  const getCurrentSessionName = () => {
    const session = sessions.find(s => s.id === currentSessionId)
    return session?.name || '新会话'
  }

  if (isLoading) {
    return (
      <div className="app-container loading">
        <div className="loading-screen">
          <div className="loading-spinner"></div>
          <p>正在加载 AgentOS...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="app-container">
      <TopBar
        sessionName={getCurrentSessionName()}
        sidebarCollapsed={sidebarCollapsed}
        rightPanelCollapsed={rightPanelCollapsed}
        onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
        onToggleRightPanel={() => setRightPanelCollapsed(!rightPanelCollapsed)}
        onNewSession={handleNewSession}
        onOpenSettings={() => setShowSettings(true)}
        onOpenFiles={() => setShowFiles(true)}
      />

      <div className="app-body">
        <Sidebar
          collapsed={sidebarCollapsed}
          sessions={sessions}
          currentSessionId={currentSessionId}
          onLoadSession={handleSwitchSession}
          onNewSession={handleNewSession}
          onOpenSettings={() => setShowSettings(true)}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onDeleteSession={deleteSession}
          onRenameSession={handleRenameSession}
        />

        <div className="main-content">
          {/* ✅ 移除 key，避免切换会话时重新挂载 */}
          <Chat
            sessionId={currentSessionId}
            onSessionUpdate={handleSessionUpdate}
          />
        </div>

        <RightPanel
          collapsed={rightPanelCollapsed}
          tools={tools}
          skills={skills}
          workflows={workflows}
          onInsertCommand={(cmd, type) => {
            window.dispatchEvent(
              new CustomEvent('insertCommand', { detail: { command: cmd, type } })
            )
          }}
          onToggleCollapse={() => setRightPanelCollapsed(!rightPanelCollapsed)}
        />
      </div>

      <div className="status-bar">
        <span>{health?.ollama ? '🟢 Ollama 运行中' : '🔴 Ollama 未连接'}</span>
        <span>📦 {health?.models || 0} 个模型</span>
        <span>🔧 {tools.length || 0} 个工具</span>
        <span>🎯 {skills.length || 0} 个技能</span>
        <span>📋 {workflows.length || 0} 个工作流</span>
        <span>📚 {health?.memory || 0} 条记忆</span>
        <span className="status-version">v17.0.0</span>
      </div>

      {showSettings && (
        <SettingsPage onClose={() => setShowSettings(false)} onReload={handleReload} />
      )}

      {showFiles && (
        <FileManagerModal onClose={() => setShowFiles(false)} />
      )}
    </div>
  )
}

export default App