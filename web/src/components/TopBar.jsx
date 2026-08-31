import React from 'react'
import './TopBar.css'

function TopBar({
  sessionName,
  sidebarCollapsed,
  rightPanelCollapsed,
  onToggleSidebar,
  onToggleRightPanel,
  onNewSession,
  onOpenSettings,
}) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="topbar-btn"
          onClick={onToggleSidebar}
          title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          {sidebarCollapsed ? '▶' : '◀'}
        </button>
        <span className="topbar-logo">🤖</span>
        <span className="topbar-title">AgentOS</span>
        <span className="topbar-version">v17.0.0</span>
      </div>

      <div className="topbar-center">
        <span className="topbar-session">{sessionName || '新会话'}</span>
      </div>

      <div className="topbar-right">
        <button
          className="topbar-btn"
          onClick={onNewSession}
          title="新建会话"
        >
          ➕
        </button>
        <button
          className="topbar-btn"
          onClick={onOpenSettings}
          title="设置"
        >
          ⚙️
        </button>
        <button
          className="topbar-btn"
          onClick={onToggleRightPanel}
          title={rightPanelCollapsed ? '展开面板' : '收起面板'}
        >
          {rightPanelCollapsed ? '◀' : '▶'}
        </button>
      </div>
    </header>
  )
}

export default TopBar