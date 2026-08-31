import React from 'react'
import './SettingsModal.css'

function SettingsModal({ onClose, health, sessions, onNewSession }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">⚙️ 设置</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="settings-grid">
            <div className="settings-item">
              <span className="settings-label">🔌 API 状态</span>
              <span className={`settings-value ${health?.status === 'ok' ? 'ok' : 'error'}`}>
                {health?.status === 'ok' ? '✅ 在线' : '⚠️ 异常'}
              </span>
            </div>
            <div className="settings-item">
              <span className="settings-label">🧠 Ollama</span>
              <span className={`settings-value ${health?.ollama ? 'ok' : 'error'}`}>
                {health?.ollama ? '✅ 运行中' : '❌ 未连接'}
              </span>
            </div>
            <div className="settings-item">
              <span className="settings-label">📦 模型</span>
              <span className="settings-value">{health?.models || 0} 个</span>
            </div>
            <div className="settings-item">
              <span className="settings-label">🔧 工具</span>
              <span className="settings-value">{health?.tools || 0} 个</span>
            </div>
            <div className="settings-item">
              <span className="settings-label">🎯 技能</span>
              <span className="settings-value">{health?.skills || 0} 个</span>
            </div>
            <div className="settings-item">
              <span className="settings-label">📋 工作流</span>
              <span className="settings-value">{health?.workflows || 0} 个</span>
            </div>
            <div className="settings-item">
              <span className="settings-label">📚 记忆</span>
              <span className="settings-value">{health?.memory || 0} 条</span>
            </div>
            <div className="settings-item">
              <span className="settings-label">💬 会话</span>
              <span className="settings-value">{sessions?.length || 0} 个</span>
            </div>
          </div>

          <div className="settings-actions">
            <button className="settings-action-btn" onClick={onNewSession}>
              ➕ 新建会话
            </button>
          </div>

          <div className="settings-footer">
            <span>AgentOS v{health?.version || '17.0.0'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SettingsModal