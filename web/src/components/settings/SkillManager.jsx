// web/src/components/settings/SkillManager.jsx
import React, { useState, useEffect } from 'react'
import { AgentAPI } from '../../services/api'

// ✅ 技能模板（前端硬编码）
const SKILL_TEMPLATE = `📄 skill.yaml:
\`\`\`yaml
name: my_skill
description: 这是我的技能描述
version: 1.0.0
category: general

tools:
  - read_file
  - write_file

model: qwen2.5:3b
timeout: 60
retries: 2

triggers:
  - 我的触发词

enabled: true
\`\`\`

📄 handler.py:
\`\`\`python
# skills/my_skill/handler.py
from core.logger import agent_logger


def handler(context) -> str:
    agent_logger.info(f"执行 my_skill: {context.user_input[:50]}...")

    # 在这里实现你的技能逻辑
    user_input = context.user_input

    # 使用工具示例
    # from tools.registry import tool_registry
    # result = tool_registry.execute("read_file", filepath="test.txt")

    return f"处理完成: {user_input}"
\`\`\``

function SkillManager() {
  const [skills, setSkills] = useState([])
  const [availableTools, setAvailableTools] = useState([])
  const [availableModels, setAvailableModels] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [showTemplate, setShowTemplate] = useState(false)
  const [editing, setEditing] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    triggers: [''],
    model: '',
    tools: [],
    prompt: '',
    enabled: true,
  })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [skillsResp, toolsResp, modelsResp] = await Promise.all([
        AgentAPI.adminListSkills(),
        AgentAPI.listTools(),
        AgentAPI.adminListModels(),
      ])
      setSkills(skillsResp.data?.skills || [])
      setAvailableTools(toolsResp.data || [])

      const models = modelsResp.data?.local || []
      setAvailableModels(models.map(m => m.name))
    } catch (e) {
      console.error('加载数据失败:', e)
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
        model: formData.model || null,
      }

      if (editing) {
        await AgentAPI.adminUpdateSkill(editing, data)
      } else {
        await AgentAPI.adminCreateSkill(data)
      }

      setShowForm(false)
      setEditing(null)
      resetForm()
      loadData()
      alert('✅ 保存成功')
    } catch (e) {
      alert('保存失败: ' + e.message)
    }
  }

  const handleDelete = async (name) => {
    if (!confirm(`确定删除技能 "${name}" 吗？`)) return
    try {
      await AgentAPI.adminDeleteSkill(name)
      loadData()
    } catch (e) {
      alert('删除失败: ' + e.message)
    }
  }

  const handleEdit = (skill) => {
    setEditing(skill.name)
    setFormData({
      name: skill.name,
      description: skill.description || '',
      triggers: skill.triggers || [''],
      model: skill.model || '',
      tools: skill.tools || [],
      prompt: skill.prompt || '',
      enabled: skill.enabled !== false,
    })
    setShowForm(true)
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      triggers: [''],
      model: '',
      tools: [],
      prompt: '',
      enabled: true,
    })
  }

  const handleTriggerChange = (index, value) => {
    const newTriggers = [...formData.triggers]
    newTriggers[index] = value
    setFormData({ ...formData, triggers: newTriggers })
  }

  const addTrigger = () => {
    setFormData({ ...formData, triggers: [...formData.triggers, ''] })
  }

  const removeTrigger = (index) => {
    const newTriggers = formData.triggers.filter((_, i) => i !== index)
    setFormData({ ...formData, triggers: newTriggers })
  }

  if (loading) return <div className="loading">加载中...</div>

  return (
    <div className="skill-manager">
      <div className="manager-header">
        <h3>🎯 技能管理 ({skills.length})</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-primary" onClick={() => { setEditing(null); resetForm(); setShowForm(true) }}>
            ➕ 新建技能
          </button>
          <button className="btn-secondary" onClick={() => setShowTemplate(!showTemplate)}>
            📄 模板
          </button>
        </div>
      </div>

      {showTemplate && (
        <div className="template-panel">
          <div className="template-header">
            <span>📄 技能模板</span>
            <button className="modal-close" onClick={() => setShowTemplate(false)}>✕</button>
          </div>
          <div className="template-body">
            <div className="hint">
              💡 在 <code>skills/</code> 目录下创建 <code>技能名/skill.yaml</code> 和 <code>技能名/handler.py</code> 即可添加新技能
            </div>
            <pre className="template-code">{SKILL_TEMPLATE}</pre>
          </div>
        </div>
      )}

      <div className="skill-list">
        {skills.length === 0 ? (
          <div className="empty-state">暂无技能，点击右上角创建</div>
        ) : (
          skills.map(skill => (
            <div key={skill.name} className={`skill-item ${!skill.enabled ? 'disabled' : ''}`}>
              <div className="skill-info">
                <div className="skill-name">{skill.name}</div>
                <div className="skill-triggers">
                  {skill.triggers?.map(t => <span key={t} className="trigger-tag">【{t}】</span>)}
                </div>
                <div className="skill-meta">
                  模型: {skill.model || '默认'} | 工具: {skill.tools?.length || 0}个
                </div>
              </div>
              <div className="skill-actions">
                <span className={`skill-status ${skill.enabled ? 'active' : 'inactive'}`}>
                  {skill.enabled ? '✅ 启用' : '⛔ 禁用'}
                </span>
                <button className="btn-edit" onClick={() => handleEdit(skill)}>✏️</button>
                <button className="btn-delete" onClick={() => handleDelete(skill.name)}>🗑️</button>
              </div>
            </div>
          ))
        )}
      </div>

      {showForm && (
        <div className="form-overlay" onClick={() => setShowForm(false)}>
          <div className="form-modal" onClick={e => e.stopPropagation()}>
            <h3>{editing ? '编辑技能' : '新建技能'}</h3>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>技能名称 *</label>
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
                <label>触发词 (多个)</label>
                {formData.triggers.map((trigger, index) => (
                  <div key={index} className="trigger-input">
                    <input
                      type="text"
                      value={trigger}
                      onChange={e => handleTriggerChange(index, e.target.value)}
                      placeholder="输入触发词"
                    />
                    {formData.triggers.length > 1 && (
                      <button type="button" onClick={() => removeTrigger(index)}>✕</button>
                    )}
                  </div>
                ))}
                <button type="button" className="btn-add-trigger" onClick={addTrigger}>
                  ➕ 添加触发词
                </button>
              </div>

              <div className="form-group">
                <label>模型</label>
                <select
                  value={formData.model}
                  onChange={e => setFormData({ ...formData, model: e.target.value })}
                >
                  <option value="">默认模型</option>
                  {availableModels.map(model => (
                    <option key={model} value={model}>{model}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>可用工具</label>
                <div className="tools-select">
                  {availableTools.map(tool => (
                    <label key={tool.name} className="tool-checkbox">
                      <input
                        type="checkbox"
                        checked={formData.tools.includes(tool.name)}
                        onChange={(e) => {
                          const newTools = e.target.checked
                            ? [...formData.tools, tool.name]
                            : formData.tools.filter(t => t !== tool.name)
                          setFormData({ ...formData, tools: newTools })
                        }}
                      />
                      [{tool.name}]
                    </label>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label>指令 (Prompt)</label>
                <textarea
                  value={formData.prompt}
                  onChange={e => setFormData({ ...formData, prompt: e.target.value })}
                  rows={6}
                  placeholder="输入技能的行为指令..."
                />
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
                <button type="submit" className="btn-primary">
                  {editing ? '更新' : '创建'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default SkillManager