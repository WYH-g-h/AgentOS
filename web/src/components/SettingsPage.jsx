// web/src/components/SettingsPage.jsx
import React, { useState } from 'react'
import {
  ModelManager,
  SkillManager,
  WorkflowManager,
  FileManager,
  SystemSettings,
  ToolManager,
} from './settings'
import './SettingsPage.css'

function SettingsPage({ onClose, onReload }) {
  const [activeTab, setActiveTab] = useState('models')

  const tabs = [
    { id: 'models', icon: '🧠', label: '模型管理' },
    { id: 'skills', icon: '🎯', label: '技能管理' },
    { id: 'workflows', icon: '📋', label: '工作流管理' },
    { id: 'tools', icon: '🔧', label: '工具管理' },
    { id: 'files', icon: '📂', label: '文件管理' },
    { id: 'system', icon: '⚙️', label: '系统设置' },
  ]

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-container" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h2>⚙️ 设置</h2>
          <button className="settings-close" onClick={onClose}>✕</button>
        </div>

        <div className="settings-body">
          <div className="settings-sidebar">
            {tabs.map(tab => (
              <button
                key={tab.id}
                className={`settings-tab ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <span className="tab-icon">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>

          <div className="settings-content">
            {activeTab === 'models' && <ModelManager />}
            {activeTab === 'skills' && <SkillManager />}
            {activeTab === 'workflows' && <WorkflowManager />}
            {activeTab === 'tools' && <ToolManager />}
            {activeTab === 'files' && <FileManager />}
            {activeTab === 'system' && <SystemSettings onReload={onReload} />}
          </div>
        </div>
      </div>
    </div>
  )
}

export default SettingsPage