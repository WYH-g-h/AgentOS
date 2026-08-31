// web/src/services/api.jsx
import axios from 'axios'

// 环境检测
const isElectron = window.location.protocol === 'file:'
const API_HOST = import.meta.env.VITE_API_HOST || 'localhost'
const API_PORT = import.meta.env.VITE_API_PORT || 8000

const API_BASE_URL = isElectron
  ? `http://${API_HOST}:${API_PORT}/api`
  : '/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (response) => {
    console.log('✅ API Response:', response.config.url, response.status)
    return response
  },
  (error) => {
    console.error('❌ API Error:', error)
    return Promise.reject(error)
  }
)

export const AgentAPI = {
  health: () => api.get('/health'),

  // 通用文件上传
  uploadFile: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 图片上传
  uploadImage: (file, sessionId) => {
    const formData = new FormData()
    formData.append('file', file)
    if (sessionId) formData.append('session_id', sessionId)
    return api.post('/vision/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 对话（非流式）
  chat: (userInput, sessionId) =>
    api.post('/chat', { user_input: userInput, session_id: sessionId }),

  // 流式对话
  chatStream: async function* (userInput, sessionId) {
    const url = API_BASE_URL + '/chat/stream'
    console.log('📡 流式请求 URL:', url)

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_input: userInput, session_id: sessionId }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.trim()) {
          try {
            const data = JSON.parse(line)
            yield data
          } catch (e) {
            console.warn('解析流式数据失败:', e)
          }
        }
      }
    }
  },

  // 获取会话历史消息
  getSessionMessages: (sessionId) => api.get(`/memory/${sessionId}/messages`),

  // 记忆列表
  listMemory: () => api.get('/memory'),

  // 添加记忆
  addMemory: (content, category) => api.post('/memory', { content, category }),

  // 删除记忆/会话
  deleteMemory: (id) => api.delete(`/memory/${id}`),

  // 重命名会话
  renameSession: (sessionId, newName) =>
    api.put(`/memory/${sessionId}/rename`, { new_name: newName }),

  // 工具/技能/工作流
  listTools: () => api.get('/tools'),
  listSkills: () => api.get('/skills'),
  listWorkflows: () => api.get('/workflows'),

  // 视觉分析
  analyzeImage: (imagePath, prompt, sessionId) =>
    api.post('/vision/analyze', {
      image_path: imagePath,
      prompt: prompt || '请详细描述这张图片的内容，用中文回答。',
      session_id: sessionId,
    }),

  // RAG
  ragSearch: (query, project = 'default', k = 3) =>
    api.post('/rag/search', { query, project, k }),
  ragAsk: (query, project = 'default') =>
    api.post('/rag/ask', { query, project }),

  // ============================================================
  // Admin API
  // ============================================================

  // --- 技能 ---
  adminListSkills: () => api.get('/admin/skills'),
  adminCreateSkill: (data) => api.post('/admin/skills', data),
  adminUpdateSkill: (name, data) => api.put(`/admin/skills/${name}`, data),
  adminDeleteSkill: (name) => api.delete(`/admin/skills/${name}`),

  // --- 工作流 ---
  adminListWorkflows: () => api.get('/admin/workflows'),
  adminCreateWorkflow: (data) => api.post('/admin/workflows', data),
  adminDeleteWorkflow: (name) => api.delete(`/admin/workflows/${name}`),

  // --- 模型 ---
  adminListModels: () => api.get('/admin/models'),
  adminSwitchModel: (modelName) => api.post('/admin/models/switch', { model_name: modelName }),
  adminConfigureCloud: (data) => api.post('/admin/models/cloud', data),
  adminDeleteCloudModel: (provider) => api.delete(`/admin/models/cloud/${provider}`),

  // --- 路径 ---
  adminGetPaths: () => api.get('/admin/paths'),
  adminUpdatePaths: (data) => api.post('/admin/paths', data),

  // --- 文件 ---
  adminListDataFiles: () => api.get('/admin/files/data'),
  adminListOutputFiles: () => api.get('/admin/files/output'),
  adminDeleteOutputFile: (filename) => api.delete(`/admin/files/output/${filename}`),
  adminClearOutput: () => api.post('/admin/files/output/clear'),

  // --- 工具管理 ---
  adminListTools: () => api.get('/admin/tools'),
  adminListCustomTools: () => api.get('/admin/tools/custom'),
  adminReloadTools: () => api.post('/admin/tools/reload'),
  adminClearTools: () => api.post('/admin/tools/clear'),

  // --- 热加载 ---
  adminReload: () => api.post('/admin/reload'),
}