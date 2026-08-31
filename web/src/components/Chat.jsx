// web/src/components/Chat.jsx
import React, { useState, useEffect, useRef } from 'react'
import MessageList from './MessageList'
import InputArea from './InputArea'
import VisionModal from './VisionModal'
import { AgentAPI } from '../services/api'
import { useSession } from '../hooks/useSession'
import './Chat.css'

function Chat({ sessionId, onSessionUpdate }) {
  const [messages, setMessages] = useState([])
  const [isThinking, setIsThinking] = useState(false)
  const [progress, setProgress] = useState(0)
  const [progressText, setProgressText] = useState('')
  const [showVisionModal, setShowVisionModal] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const [streamError, setStreamError] = useState(null)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const messagesEndRef = useRef(null)
  const isStreaming = useRef(false)

  const { loadSessionMessages } = useSession()

  useEffect(() => {
    const loadMessages = async () => {
      if (!sessionId) {
        setMessages([])
        return
      }

      console.log('📌 Chat 加载会话消息:', sessionId)
      setIsLoadingHistory(true)
      try {
        const history = await loadSessionMessages(sessionId)
        setMessages(history || [])
      } catch (e) {
        console.error('加载历史消息失败:', e)
        setMessages([])
      } finally {
        setIsLoadingHistory(false)
      }
    }

    loadMessages()
  }, [sessionId, loadSessionMessages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (text) => {
    if (!text.trim() || isStreaming.current) return

    setMessages(prev => [...prev, { role: 'user', content: text }])
    setInputValue('')
    setIsThinking(true)
    setProgress(0)
    setProgressText('思考中...')
    setStreamError(null)

    try {
      isStreaming.current = true
      let fullResponse = ''
      let lastSessionId = sessionId

      for await (const chunk of AgentAPI.chatStream(text, sessionId)) {
        if (chunk.session_id) {
          lastSessionId = chunk.session_id
          onSessionUpdate?.(chunk.session_id)
        }

        if (chunk.content) {
          fullResponse += chunk.content
          const pct = Math.min(90, Math.floor(fullResponse.length / 1.5))
          setProgress(pct)
          setProgressText('生成回复中...')
        }

        if (chunk.done) {
          setProgress(100)
          setProgressText('完成')
        }
      }

      if (fullResponse) {
        setMessages(prev => [...prev, { role: 'assistant', content: fullResponse }])
        if (lastSessionId) {
          onSessionUpdate?.(lastSessionId)
        }
      } else if (!streamError) {
        setMessages(prev => [
          ...prev,
          { role: 'system', content: '⚠️ 服务返回空响应' },
        ])
      }

    } catch (error) {
      console.error('发送消息失败:', error)
      setStreamError(error.message)
      setMessages(prev => [
        ...prev,
        { role: 'system', content: `❌ 发送失败: ${error.message}` },
      ])
    } finally {
      isStreaming.current = false
      setIsThinking(false)
      setProgress(0)
      setProgressText('')
    }
  }

  const handleInsertCommand = (command, type) => {
    const symbols = {
      workflow: `(${command})`,
      skill: `【${command}】`,
      tool: `[${command}]`,
    }
    const formatted = symbols[type] || command
    const current = inputValue
    setInputValue(current + (current && !current.endsWith(' ') ? ' ' : '') + formatted + ' ')
  }

  // 监听自定义事件（插入命令）
  useEffect(() => {
    const handler = (e) => {
      const { command, type } = e.detail
      handleInsertCommand(command, type)
    }
    window.addEventListener('insertCommand', handler)
    return () => window.removeEventListener('insertCommand', handler)
  }, [])

  if (isLoadingHistory) {
    return (
      <div className="chat-container">
        <div className="chat-messages" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
          <div style={{ color: '#6c757d', fontSize: '14px' }}>加载会话中...</div>
        </div>
        <div className="chat-input-wrapper">
          <InputArea
            value={inputValue}
            onChange={setInputValue}
            onSend={handleSend}
            onOpenVision={() => setShowVisionModal(true)}
            isThinking={isThinking}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="chat-container">
      <div className="chat-messages">
        <MessageList
          messages={messages}
          isThinking={isThinking}
          progress={progress}
          progressText={progressText}
          messagesEndRef={messagesEndRef}
          streamError={streamError}
        />
      </div>

      <div className="chat-input-wrapper">
        <InputArea
          value={inputValue}
          onChange={setInputValue}
          onSend={handleSend}
          onOpenVision={() => setShowVisionModal(true)}
          isThinking={isThinking}
        />
      </div>

      <div className="chat-hints">
        <span>💡 试试: </span>
        <button className="hint-btn" onClick={() => handleInsertCommand('分析', 'skill')}>【分析】</button>
        <button className="hint-btn" onClick={() => handleInsertCommand('创建', 'skill')}>【创建】</button>
        <button className="hint-btn" onClick={() => handleInsertCommand('生成代码', 'workflow')}>(生成代码)</button>
        <button className="hint-btn" onClick={() => handleInsertCommand('读取文件', 'tool')}>[读取文件]</button>
        <button className="hint-btn" onClick={() => handleInsertCommand('写入文件', 'tool')}>[写入文件]</button>
      </div>

      {showVisionModal && (
        <VisionModal onClose={() => setShowVisionModal(false)} sessionId={sessionId} />
      )}
    </div>
  )
}

export default Chat