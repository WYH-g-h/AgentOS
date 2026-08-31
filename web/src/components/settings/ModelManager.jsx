// web/src/components/settings/ModelManager.jsx
import React, { useState, useEffect } from 'react'
import { AgentAPI } from '../../services/api'

function ModelManager() {
  const [models, setModels] = useState({ local: [], cloud: [], all: [] })
  const [currentModel, setCurrentModel] = useState('')
  const [loading, setLoading] = useState(true)
  const [cloudConfig, setCloudConfig] = useState({
    provider: 'openai',
    model_name: 'gpt-3.5-turbo',
    api_key: '',
    base_url: '',
  })

  useEffect(() => {
    loadModels()
  }, [])

  const loadModels = async () => {
    try {
      const resp = await AgentAPI.adminListModels()
      setModels({
        local: resp.data?.local || [],
        cloud: resp.data?.cloud || [],
        all: resp.data?.all || [],
      })
      setCurrentModel(resp.data?.current || '')
    } catch (e) {
      console.error('加载模型失败:', e)
    } finally {
      setLoading(false)
    }
  }

  const switchModel = async (modelName) => {
    try {
      // 检查是否是云模型
      const isCloud = models.all.some(m => m.name === modelName && m.type === 'cloud')
      if (isCloud) {
        if (!confirm(`切换到云模型 ${modelName}？\n云模型需要网络，响应可能较慢。`)) {
           return
        }
      }

      await AgentAPI.adminSwitchModel(modelName)
      setCurrentModel(modelName)
      alert(`✅ 已切换到 ${modelName}`)
    } catch (e) {
      alert('切换失败: ' + e.message)
    }
  }

  const saveCloudModel = async () => {
    if (!cloudConfig.api_key) {
      alert('请填写 API Key')
      return
    }
    try {
      await AgentAPI.adminConfigureCloud(cloudConfig)
      alert('✅ 云模型已配置')
      loadModels()
      setCloudConfig({ ...cloudConfig, api_key: '' })
    } catch (e) {
      alert('保存失败: ' + e.message)
    }
  }

  const deleteCloudModel = async (provider) => {
    if (!confirm(`确定删除 ${provider} 配置吗？`)) return
    try {
      await AgentAPI.adminDeleteCloudModel(provider)
      loadModels()
    } catch (e) {
      alert('删除失败: ' + e.message)
    }
  }

  if (loading) return <div className="loading">加载中...</div>

  return (
    <div className="model-manager">
      <h3>🧠 模型管理</h3>

      <div className="current-model">
        <span>当前模型: </span>
        <strong>{currentModel || '未选择'}</strong>
        <button className="btn-refresh" onClick={loadModels}>🔄 刷新</button>
      </div>

      {/* 本地模型 */}
      <div className="model-section">
        <h4>📦 本地模型 (Ollama)</h4>
        <div className="model-grid">
          {models.local.length === 0 ? (
            <div className="empty-state">没有检测到本地模型，请确保 Ollama 已启动</div>
          ) : (
            models.local.map(m => (
              <div
                key={m.name}
                className={`model-card ${m.name === currentModel ? 'active' : ''}`}
                onClick={() => switchModel(m.name)}
              >
                <div className="model-name">{m.name}</div>
                {m.size && <div className="model-size">{(m.size / 1024 / 1024 / 1024).toFixed(1)} GB</div>}
                {m.name === currentModel && <span className="model-badge">✓ 当前</span>}
              </div>
            ))
          )}
        </div>
      </div>

      {/* ✅ 云模型 */}
      <div className="model-section">
        <h4>☁️ 云模型 API</h4>

        {models.cloud.length > 0 && (
          <div className="cloud-list">
            {models.cloud.map(c => (
              <div key={c.provider} className="cloud-item">
                <span><strong>{c.provider}</strong>: {c.model_name}</span>
                <button className="btn-delete-sm" onClick={() => deleteCloudModel(c.provider)}>
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        {/* ✅ 云模型卡片（可点击切换） */}
        {models.all.filter(m => m.type === 'cloud').map(m => (
          <div
            key={m.name}
            className={`model-card ${m.name === currentModel ? 'active' : ''}`}
            onClick={() => switchModel(m.name)}
          >
            <div className="model-name">☁️ {m.name}</div>
            <div className="model-size">{m.provider}</div>
            {m.name === currentModel && <span className="model-badge">✓ 当前</span>}
          </div>
        ))}

        <div className="cloud-form">
          <select
            value={cloudConfig.provider}
            onChange={e => setCloudConfig({ ...cloudConfig, provider: e.target.value })}
          >
            <option value="openai">OpenAI</option>
            <option value="deepseek">DeepSeek</option>
            <option value="custom">自定义</option>
          </select>
          <input
            type="text"
            placeholder="模型名称 (如 gpt-3.5-turbo)"
            value={cloudConfig.model_name}
            onChange={e => setCloudConfig({ ...cloudConfig, model_name: e.target.value })}
          />
          <input
            type="password"
            placeholder="API Key"
            value={cloudConfig.api_key}
            onChange={e => setCloudConfig({ ...cloudConfig, api_key: e.target.value })}
          />
          {cloudConfig.provider === 'custom' && (
            <input
              type="text"
              placeholder="API Base URL"
              value={cloudConfig.base_url}
              onChange={e => setCloudConfig({ ...cloudConfig, base_url: e.target.value })}
            />
          )}
          <button className="btn-primary" onClick={saveCloudModel}>保存</button>
        </div>
      </div>
    </div>
  )
}

export default ModelManager