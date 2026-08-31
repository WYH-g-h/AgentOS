// web/src/hooks/useAgentOS.jsx
import { useState, useEffect, useCallback, useRef } from 'react'
import { AgentAPI } from '../services/api'

export function useAgentOS() {
  const [messages, setMessages] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [sessionName, setSessionName] = useState('新会话')
  const [sessions, setSessions] = useState([])
  const [isThinking, setIsThinking] = useState(false)
  const [progress, setProgress] = useState(0)
  const [progressText, setProgressText] = useState('')
  const [health, setHealth] = useState(null)
  const [tools, setTools] = useState([])
  const [skills, setSkills] = useState([])
  const [workflows, setWorkflows] = useState([])
  const isStreaming = useRef(false)
  const abortControllerRef = useRef(null)

  // 加载健康状态
  const loadHealth = useCallback(async () => {
    try {
      const resp = await AgentAPI.health()
      setHealth(resp.data)
    } catch (e) {
      console.error('Health check failed:', e)
      setHealth(null)
    }
  }, [])

  // 加载列表
  const loadLists = useCallback(async () => {
    try {
      const [toolsResp, skillsResp, workflowsResp] = await Promise.all([
        AgentAPI.listTools(),
        AgentAPI.listSkills(),
        AgentAPI.listWorkflows(),
      ])
      setTools(toolsResp.data || [])
      setSkills(skillsResp.data || [])
      setWorkflows(workflowsResp.data || [])
    } catch (e) {
      console.error('Load lists failed:', e)
    }
  }, [])

  // 加载会话列表
  const loadSessions = useCallback(async () => {
    try {
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
      console.error('Load sessions failed:', e)
    }
  }, [])

  // 初始化
  useEffect(() => {
    loadHealth()
    loadLists()
    loadSessions()

    const interval = setInterval(() => {
      loadHealth()
    }, 30000)

    return () => clearInterval(interval)
  }, [loadHealth, loadLists, loadSessions])

  // 发送消息
  const sendMessage = useCallback(
    async (text) => {
      if (!text.trim()) return
      if (isStreaming.current) {
        // 如果正在流式传输，取消当前请求
        if (abortControllerRef.current) {
          abortControllerRef.current.abort()
          abortControllerRef.current = null
        }
        return
      }

      // 添加用户消息
      setMessages((prev) => [...prev, { role: 'user', content: text }])
      setIsThinking(true)
      setProgress(0)
      setProgressText('思考中...')

      try {
        isStreaming.current = true
        let fullResponse = ''
        let lastSessionId = sessionId

        // 使用 AgentAPI.chatStream
        for await (const chunk of AgentAPI.chatStream(text, sessionId)) {
          if (chunk.session_id) {
            lastSessionId = chunk.session_id
            if (!sessionId) setSessionId(chunk.session_id)
          }

          if (chunk.content) {
            fullResponse += chunk.content
            if (fullResponse.length > 20) {
              const pct = Math.min(90, Math.floor(fullResponse.length / 2))
              setProgress(pct)
              setProgressText('生成回复中...')
            }
          }

          if (chunk.done) {
            setProgress(100)
            setProgressText('完成')
          }
        }

        // 完成
        if (fullResponse) {
          setMessages((prev) => [...prev, { role: 'assistant', content: fullResponse }])
          if (lastSessionId) setSessionId(lastSessionId)
        }

        setIsThinking(false)
        setProgress(0)
        setProgressText('')
      } catch (error) {
        console.error('Send message failed:', error)
        setMessages((prev) => [
          ...prev,
          { role: 'system', content: `❌ 发送失败: ${error.message}` },
        ])
        setIsThinking(false)
        setProgress(0)
        setProgressText('')
      } finally {
        isStreaming.current = false
        loadSessions()
      }
    },
    [sessionId, loadSessions]
  )

  // 新建会话
  const newSession = useCallback(() => {
    setMessages([])
    setSessionId(null)
    setSessionName('新会话')
  }, [])

  // 加载会话
  const loadSession = useCallback(
    async (sid) => {
      setSessionId(sid)
      setSessionName(sid.slice(0, 20))
      setMessages([])
      try {
        const resp = await AgentAPI.listMemory()
        const items = resp.data?.items || []
        const history = items
          .filter((item) => item.id === sid || item.category === 'session')
          .slice(0, 20)
        for (const item of history) {
          if (item.category === 'user_msg') {
            setMessages((prev) => [...prev, { role: 'user', content: item.content }])
          } else if (item.category === 'assistant_msg') {
            setMessages((prev) => [...prev, { role: 'assistant', content: item.content }])
          }
        }
      } catch (e) {
        console.error('Load session failed:', e)
      }
    },
    []
  )

  return {
    messages,
    sessionId,
    sessionName,
    sessions,
    isThinking,
    progress,
    progressText,
    health,
    tools,
    skills,
    workflows,
    sendMessage,
    newSession,
    loadSession,
    loadSessions,
  }
}