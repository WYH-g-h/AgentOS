// web/src/components/settings/WorkflowManager.jsx
import React, { useState, useEffect } from 'react'
import { AgentAPI } from '../../services/api'

// ✅ 工作流模板（前端硬编码）
const WORKFLOW_TEMPLATE = `📄 workflow.yaml:
\`\`\`yaml
name: my_workflow
description: 这是我的工作流描述
version: 1.0.0

triggers:
  - 我的触发词

config:
  stop_on_error: true

enabled: true
\`\`\`

📄 steps.yaml:
\`\`\`yaml
- name: step1
  skill: analyze
  params:
    description: "分析输入"
  depends_on: []
  condition: null

- name: step2
  skill: create
  params:
    output: "result.txt"
  depends_on: [step1]
  condition: null
\`\`\``

function WorkflowManager() {
  const [workflows, setWorkflows] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [showTemplate, setShowTemplate] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    triggers: [''],
    steps: [{ name: '', tool: '', params: {} }],
    enabled: true,
  })

  useEffect(() => {
    loadWorkflows()
  }, [])

  const loadWorkflows = async () => {
    try {
      const resp = await AgentAPI.adminListWorkflows()
      setWorkflows(resp.data?.workflows || [])
    } catch (e) {
      console.error('加载工作流失败:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const data = {
        ...formData,
        triggers: formData.triggers.filter(t => t.trim()),
        steps: formData.steps.filter(s => s.name && s.tool),
      }
      await AgentAPI.adminCreateWorkflow(data)
      setShowForm(false)
      resetForm()
      loadWorkflows()
      alert('✅ 工作流创建成功')
    } catch (e) {
      alert('创建失败: ' + e.message)
    }
  }

  const handleDelete = async (name) => {
    if (!confirm(`确定删除工作流 "${name}" 吗？`)) return
    try {
      await AgentAPI.adminDeleteWorkflow(name)
      loadWorkflows()
    } catch (e) {
      alert('删除失败: ' + e.message)
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      triggers: [''],
      steps: [{ name: '', tool: '', params: {} }],
      enabled: true,
    })
  }

  const addStep = () => {
    setFormData({
      ...formData,
      steps: [...formData.steps, { name: '', tool: '', params: {} }],
    })
  }

  const removeStep = (index) => {
    const newSteps = formData.steps.filter((_, i) => i !== index)
    setFormData({ ...formData, steps: newSteps })
  }

  const updateStep = (index, field, value) => {
    const newSteps = [...formData.steps]
    newSteps[index][field] = value
    setFormData({ ...formData, steps: newSteps })
  }

  if (loading) return <div className="loading">加载中...</div>

  return (
    <div className="skill-manager">
      <div className="manager-header">
        <h3>📋 工作流管理 ({workflows.length})</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-primary" onClick={() => { resetForm(); setShowForm(true) }}>
            ➕ 新建工作流
          </button>
          <button className="btn-secondary" onClick={() => setShowTemplate(!showTemplate)}>
            📄 模板
          </button>
        </div>
      </div>

      {showTemplate && (
        <div className="template-panel">
          <div className="template-header">
            <span>📄 工作流模板</span>
            <button className="modal-close" onClick={() => setShowTemplate(false)}>✕</button>
          </div>
          <div className="template-body">
            <div className="hint">
              💡 在 <code>workflows/</code> 目录下创建 <code>工作流名/workflow.yaml</code> 和 <code>工作流名/steps.yaml</code> 即可添加新工作流
            </div>
            <pre className="template-code">{WORKFLOW_TEMPLATE}</pre>
          </div>
        </div>
      )}

      <div className="skill-list">
        {workflows.length === 0 ? (
          <div className="empty-state">暂无工作流</div>
        ) : (
          workflows.map(wf => (
            <div key={wf.name} className={`skill-item ${!wf.enabled ? 'disabled' : ''}`}>
              <div className="skill-info">
                <div className="skill-name">📋 {wf.name}</div>
                <div className="skill-triggers">
                  {wf.triggers?.map(t => <span key={t} className="trigger-tag">({t})</span>)}
                </div>
                <div className="skill-meta">
                  {wf.description || ''} | {wf.steps || 0} 步
                </div>
              </div>
              <div className="skill-actions">
                <span className={`skill-status ${wf.enabled ? 'active' : 'inactive'}`}>
                  {wf.enabled ? '✅ 启用' : '⛔ 禁用'}
                </span>
                <button className="btn-delete" onClick={() => handleDelete(wf.name)}>🗑️</button>
              </div>
            </div>
          ))
        )}
      </div>

      {showForm && (
        <div className="form-overlay" onClick={() => setShowForm(false)}>
          <div className="form-modal" onClick={e => e.stopPropagation()}>
            <h3>新建工作流</h3>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>工作流名称 *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label>描述</label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={e => setFormData({ ...formData, description: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>触发词</label>
                <input
                  type="text"
                  value={formData.triggers[0] || ''}
                  onChange={e => setFormData({ ...formData, triggers: [e.target.value] })}
                  placeholder="输入触发词"
                />
              </div>

              <div className="form-group">
                <label>步骤</label>
                {formData.steps.map((step, index) => (
                  <div key={index} style={{ marginBottom: 8, padding: 8, background: '#f8f9fa', borderRadius: 4 }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input
                        placeholder="步骤名称"
                        value={step.name}
                        onChange={e => updateStep(index, 'name', e.target.value)}
                        style={{ flex: 1 }}
                      />
                      <input
                        placeholder="工具名"
                        value={step.tool}
                        onChange={e => updateStep(index, 'tool', e.target.value)}
                        style={{ flex: 1 }}
                      />
                      {formData.steps.length > 1 && (
                        <button type="button" className="btn-delete-sm" onClick={() => removeStep(index)}>✕</button>
                      )}
                    </div>
                  </div>
                ))}
                <button type="button" className="btn-add-trigger" onClick={addStep}>
                  ➕ 添加步骤
                </button>
              </div>

              <div className="form-group">
                <label>
                  <input
                    type="checkbox"
                    checked={formData.enabled}
                    onChange={e => setFormData({ ...formData, enabled: e.target.checked })}
                  />
                  启用
                </label>
              </div>

              <div className="form-actions">
                <button type="button" className="btn-cancel" onClick={() => setShowForm(false)}>
                  取消
                </button>
                <button type="submit" className="btn-primary">创建</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default WorkflowManager