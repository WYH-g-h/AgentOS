// web/src/components/RightPanel.jsx
import React from 'react'
import './RightPanel.css'

function RightPanel({
  collapsed,
  tools = [],
  skills = [],
  workflows = [],
  onInsertCommand,
  onToggleCollapse,
}) {
  const safeTools = Array.isArray(tools) ? tools : []
  const safeSkills = Array.isArray(skills) ? skills : []
  const safeWorkflows = Array.isArray(workflows) ? workflows : []

  if (collapsed) {
    return (
      <aside className="right-panel right-panel-collapsed">
        <button className="right-panel-expand-btn" onClick={onToggleCollapse} title="展开">
          ◀
        </button>
      </aside>
    )
  }

  return (
    <aside className="right-panel">
      <div className="right-panel-header">
        <button className="right-panel-collapse-btn" onClick={onToggleCollapse} title="收起">
          ▶ 收起
        </button>
      </div>

      {/* 工作流 */}
      {safeWorkflows.length > 0 && (
        <div className="right-section">
          <div className="right-section-title">📋 工作流</div>
          <div className="right-grid">
            {safeWorkflows.map((wf) => {
              // 使用后端返回的 display_name 或 name
              const displayName = wf.display_name || wf.name
              const key = wf.name || wf.id || `wf-${Math.random()}`
              return (
                <button
                  key={key}
                  className="right-tag workflow"
                  onClick={() => onInsertCommand(displayName, 'workflow')}
                >
                  ({displayName})
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* 技能 */}
      {safeSkills.length > 0 && (
        <div className="right-section">
          <div className="right-section-title">🎯 技能</div>
          <div className="right-grid">
            {safeSkills.map((skill) => {
              // 使用后端返回的 display_name 或 name
              const displayName = skill.display_name || skill.name
              const key = skill.name || skill.id || `skill-${Math.random()}`
              return (
                <button
                  key={key}
                  className="right-tag skill"
                  onClick={() => onInsertCommand(displayName, 'skill')}
                >
                  【{displayName}】
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* 工具 */}
      {safeTools.length > 0 && (
        <div className="right-section">
          <div className="right-section-title">🔧 工具</div>
          <div className="right-grid">
            {safeTools.map((tool) => {
              // 使用后端返回的 display_name
              const displayName = tool.display_name || tool.name
              const key = tool.name || tool.id || `tool-${Math.random()}`
              return (
                <button
                  key={key}
                  className="right-tag tool"
                  onClick={() => onInsertCommand(displayName, 'tool')}
                >
                  [{displayName}]
                </button>
              )
            })}
          </div>
        </div>
      )}
    </aside>
  )
}

export default RightPanel