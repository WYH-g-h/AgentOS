// web/src/components/MessageList.jsx
import React from 'react'
import './MessageList.css'

function MessageList({
  messages,
  isThinking,
  progress,
  progressText,
  messagesEndRef,
  streamError,
}) {
  if (messages.length === 0 && !isThinking && !streamError) {
    return (
      <div className="message-list empty">
        <div className="empty-state">
          <div className="empty-icon">🤖</div>
          <div className="empty-title">有什么我能帮你的？</div>
          <div className="empty-desc">输入消息开始对话</div>
        </div>
      </div>
    )
  }

  return (
    <div className="message-list">
      {messages.map((msg, index) => {
        const isRoute = msg.content?.startsWith('🧭') || false
        const isSystem = msg.role === 'system'

        if (isRoute) {
          return (
            <div key={index} className="message route">
              <div className="message-bubble route-bubble">{msg.content}</div>
            </div>
          )
        }

        if (isSystem) {
          const isError = msg.content?.startsWith('❌')
          return (
            <div key={index} className="message system">
              <div className={`message-bubble system-bubble ${isError ? 'error' : ''}`}>
                {isError ? '⚠️ ' : 'ℹ️ '}{msg.content}
              </div>
            </div>
          )
        }

        const isUser = msg.role === 'user'
        return (
          <div key={index} className={`message ${isUser ? 'user' : 'assistant'}`}>
            {!isUser && <div className="message-avatar">🤖</div>}
            <div className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
              {msg.content}
            </div>
            {isUser && <div className="message-avatar user-avatar">🧑</div>}
          </div>
        )
      })}

      {/* ✅ 错误信息 */}
      {streamError && (
        <div className="message system">
          <div className="message-bubble system-bubble error">
            ❌ 流式连接错误: {streamError}
          </div>
        </div>
      )}

      {/* 思考状态 */}
      {isThinking && (
        <div className="message thinking">
          <div className="message-avatar">🤖</div>
          <div className="message-bubble thinking-bubble">
            <div className="thinking-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
            {progress > 0 && (
              <div className="thinking-progress">
                <div className="thinking-progress-bar">
                  <div className="thinking-progress-fill" style={{ width: `${progress}%` }} />
                </div>
                <span className="thinking-progress-text">{progressText || '思考中...'} {progress}%</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  )
}

export default MessageList