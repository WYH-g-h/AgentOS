// web/src/components/InputArea.jsx
import React, { useState, useEffect, useRef } from 'react'
import { AgentAPI } from '../services/api'
import './InputArea.css'

function InputArea({ value, onChange, onSend, onOpenVision, isThinking }) {
    const textareaRef = useRef(null)
    const fileInputRef = useRef(null)
    const [uploading, setUploading] = useState(false)

    // 监听自定义事件
    useEffect(() => {
        const handleInsertCommand = (e) => {
            const { command, type } = e.detail
            const symbols = {
                workflow: `(${command})`,
                skill: `【${command}】`,
                tool: `[${command}]`,
            }
            const formatted = symbols[type] || command
            const current = value || ''
            const newValue = current + (current && !current.endsWith(' ') ? ' ' : '') + formatted + ' '
            onChange(newValue)
            textareaRef.current?.focus()
        }
        window.addEventListener('insertCommand', handleInsertCommand)
        return () => window.removeEventListener('insertCommand', handleInsertCommand)
    }, [value, onChange])

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto'
            textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 100) + 'px'
        }
    }, [value])

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            onSend(value)
        }
    }

    // 文件上传处理
    const handleFileUpload = async (e) => {
        const file = e.target.files[0]
        if (!file) return

        setUploading(true)
        try {
            const resp = await AgentAPI.uploadFile(file)
            if (resp.data?.success) {
                const savedPath = resp.data.saved_as || resp.data.path
                alert(`✅ 文件已上传: ${resp.data.filename}\n保存为: ${savedPath}`)
                // 可选：自动插入读取命令
                const readCmd = `[读取文件] ${savedPath}`
                onChange(value + (value && !value.endsWith(' ') ? ' ' : '') + readCmd + ' ')
                textareaRef.current?.focus()
            } else {
                alert(`上传失败: ${resp.data?.error || '未知错误'}`)
            }
        } catch (err) {
            alert(`上传失败: ${err.message}`)
        } finally {
            setUploading(false)
            e.target.value = '' // 清空 input 以便重复选择同一文件
        }
    }

    return (
        <div className="input-area">
            <div className="input-row">
                <textarea
                    ref={textareaRef}
                    className="input-textarea"
                    placeholder="输入你的问题..."
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    rows={1}
                    disabled={isThinking || uploading}
                />
                <input
                    ref={fileInputRef}
                    type="file"
                    style={{ display: 'none' }}
                    onChange={handleFileUpload}
                />
                <button
                    className="input-btn vision-btn"
                    onClick={() => fileInputRef.current?.click()}
                    title="上传文件"
                    disabled={isThinking || uploading}
                >
                    {uploading ? '⏳' : '📎'}
                </button>
                <button
                    className="input-btn vision-btn"
                    onClick={onOpenVision}
                    title="识图"
                    disabled={isThinking}
                >
                    🖼️
                </button>
                <button
                    className="input-btn send-btn"
                    onClick={() => onSend(value)}
                    disabled={isThinking || !value.trim()}
                >
                    {isThinking ? '⏳' : '发送'}
                </button>
            </div>
            <div className="input-hint">
                按 Enter 发送 · Shift+Enter 换行 · 📎 上传文件 · 🖼️ 识图
            </div>
        </div>
    )
}

export default InputArea