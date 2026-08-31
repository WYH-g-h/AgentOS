// src/components/Sidebar.jsx
import React, { useState } from 'react'
import './Sidebar.css'

function Sidebar({
  collapsed,
  sessions,
  currentSessionId,
  onLoadSession,
  onNewSession,
  onOpenSettings,
  onToggleCollapse,
  onDeleteSession,
  onRenameSession,
}) {
  const [hoveredId, setHoveredId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')

  if (collapsed) {
    return (
      <aside className="sidebar sidebar-collapsed">
        <button className="sidebar-expand-btn" onClick={onToggleCollapse} title="展开">
          ▶
        </button>
        <button className="sidebar-expand-btn" onClick={onNewSession} title="新建会话">
          ➕
        </button>
        <button className="sidebar-expand-btn" onClick={onOpenSettings} title="设置">
          ⚙️
        </button>
      </aside>
    )
  }

  const handleRename = (sessionId) => {
    const session = sessions.find(s => s.id === sessionId)
    if (session) {
      setEditName(session.name || '新会话')
      setEditingId(sessionId)
    }
  }

  const handleRenameSubmit = (sessionId) => {
    if (editName.trim()) {
        console.log('📝 提交重命名:', sessionId, editName.trim())
        onRenameSession?.(sessionId, editName.trim())
    }
    setEditingId(null)
    setEditName('')
}

  const handleRenameKeyDown = (e, sessionId) => {
    if (e.key === 'Enter') {
      handleRenameSubmit(sessionId)
    } else if (e.key === 'Escape') {
      setEditingId(null)
      setEditName('')
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <button className="sidebar-collapse-btn" onClick={onToggleCollapse} title="收起">
          ◀ 收起
        </button>
      </div>

      <button className="sidebar-new-btn" onClick={onNewSession}>
        ➕ 新建会话
      </button>

      <div className="sidebar-section">
        <div className="sidebar-section-title">📂 历史会话</div>
        <div className="sidebar-session-list">
          {sessions.length === 0 ? (
            <div className="sidebar-empty">暂无会话</div>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                className={`sidebar-session-item ${s.id === currentSessionId ? 'active' : ''}`}
                onMouseEnter={() => setHoveredId(s.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                {editingId === s.id ? (
                  // 编辑模式
                  <input
                    className="sidebar-session-edit-input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onBlur={() => handleRenameSubmit(s.id)}
                    onKeyDown={(e) => handleRenameKeyDown(e, s.id)}
                    autoFocus
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  // 显示模式
                  <span
                    className="sidebar-session-name"
                    onClick={() => {
                        console.log('🔄 点击会话:', s.id)
                        onLoadSession(s.id)
                    }}
                  >
                     {s.name || s.id.slice(0, 20)}
                     {s.messageCount > 0 && (
                        <span className="sidebar-session-count">{s.messageCount}</span>
                     )}
                  </span>
                )}

                {hoveredId === s.id && editingId !== s.id && (
                  <div className="sidebar-session-actions">
                    <button
                      className="sidebar-session-action rename"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleRename(s.id)
                      }}
                      title="重命名"
                    >
                      ✏️
                    </button>
                    {onDeleteSession && (
                      <button
                        className="sidebar-session-action delete"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (window.confirm(`删除会话 "${s.name || '新会话'}"？`)) {
                            onDeleteSession(s.id)
                          }
                        }}
                        title="删除会话"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      <div className="sidebar-footer">
        <button className="sidebar-footer-btn" onClick={onOpenSettings}>
          ⚙️ 设置
        </button>
      </div>
    </aside>
  )
}

export default Sidebar