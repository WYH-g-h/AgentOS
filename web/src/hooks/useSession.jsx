// web/src/hooks/useSession.jsx
import { useState, useEffect, useCallback } from 'react'
import { AgentAPI } from '../services/api'

export function useSession() {
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  const loadSessions = useCallback(async () => {
    try {
      setIsLoading(true)
      const resp = await AgentAPI.listMemory()
      const items = resp.data?.items || []

      const sessionMap = new Map()
      for (const item of items) {
        if (item.category === 'session' || item.category === 'session_meta') {
          const sid = item.id
          if (!sessionMap.has(sid)) {
            sessionMap.set(sid, {
              id: sid,
              name: item.content?.slice(0, 30) || sid.slice(0, 20),
              createdAt: item.time || new Date().toISOString(),
              messageCount: 0,
            })
          }
        } else if (item.category === 'user_msg' || item.category === 'assistant_msg') {
          const sid = item.session_id || item.id
          if (sessionMap.has(sid)) {
            const s = sessionMap.get(sid)
            s.messageCount = (s.messageCount || 0) + 1
          }
        }
      }

      setSessions(Array.from(sessionMap.values()))
    } catch (e) {
      console.error('加载会话失败:', e)
      try {
        const saved = localStorage.getItem('agentos_sessions')
        if (saved) {
          setSessions(JSON.parse(saved))
        }
      } catch (e2) {}
    } finally {
      setIsLoading(false)
    }
  }, [])

  // 加载会话历史消息
  const loadSessionMessages = useCallback(async (sessionId) => {
    if (!sessionId) return []

    try {
      const resp = await AgentAPI.getSessionMessages(sessionId)
      return resp.data?.messages || []
    } catch (e) {
      console.error('加载会话消息失败:', e)
      return []
    }
  }, [])

  const createSession = useCallback(async (name) => {
    try {
      const resp = await AgentAPI.addMemory(name || '新会话', 'session_meta')
      console.log('📝 创建会话响应:', resp.data)
      if (resp.data?.success && resp.data?.session_id) {
        await loadSessions()
        const sid = resp.data.session_id
        console.log('✅ 会话已创建:', sid)
        return sid
      }
    } catch (e) {
      console.error('创建会话失败:', e)
    }
    // 降级：本地创建
    const sid = `session_${Date.now()}`
    setSessions(prev => [...prev, { id: sid, name: name || '新会话', messageCount: 0 }])
    localStorage.setItem('agentos_sessions', JSON.stringify([
      ...sessions, { id: sid, name: name || '新会话', messageCount: 0 }
    ]))
    return sid
  }, [sessions, loadSessions])

  // 调用后端 /rename 端点
  const renameSession = useCallback(async (sessionId, newName) => {
    if (!newName || !newName.trim()) return false

    try {
      console.log('📝 重命名会话:', sessionId, '→', newName)

      // 调用后端重命名 API
      await AgentAPI.renameSession(sessionId, newName)

      // 立即更新本地状态（让 UI 马上显示新名称）
      setSessions(prev => prev.map(s =>
        s.id === sessionId ? { ...s, name: newName.trim() } : s
      ))

      // 后台刷新列表，保持同步
      await loadSessions()
      return true
    } catch (e) {
      console.error('重命名会话失败:', e)
      // 降级：本地更新
      setSessions(prev => prev.map(s =>
        s.id === sessionId ? { ...s, name: newName.trim() } : s
      ))
      localStorage.setItem('agentos_sessions', JSON.stringify(
        sessions.map(s => s.id === sessionId ? { ...s, name: newName.trim() } : s)
      ))
      return true
    }
  }, [sessions, loadSessions])

  const deleteSession = useCallback(async (sessionId) => {
    try {
      const resp = await AgentAPI.deleteMemory(sessionId)
      if (resp.data?.success) {
        await loadSessions()
        return true
      }
    } catch (e) {
      console.error('删除会话失败:', e)
    }
    setSessions(prev => prev.filter(s => s.id !== sessionId))
    localStorage.setItem('agentos_sessions', JSON.stringify(
      sessions.filter(s => s.id !== sessionId)
    ))
    if (currentSessionId === sessionId) {
      setCurrentSessionId(null)
      localStorage.removeItem('agentos_current_session')
    }
    return true
  }, [sessions, currentSessionId, loadSessions])

  const switchSession = useCallback((sessionId) => {
    console.log('📌 useSession switchSession:', sessionId)
    setCurrentSessionId(sessionId)
    localStorage.setItem('agentos_current_session', sessionId)
  }, [])

  useEffect(() => {
    const saved = localStorage.getItem('agentos_current_session')
    if (saved) {
      setCurrentSessionId(saved)
    }
    loadSessions()
  }, [loadSessions])

  return {
    sessions,
    currentSessionId,
    isLoading,
    loadSessions,
    loadSessionMessages,
    createSession,
    deleteSession,
    renameSession,
    switchSession,
    setCurrentSessionId,
  }
}