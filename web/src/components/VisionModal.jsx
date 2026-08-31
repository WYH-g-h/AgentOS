import React, { useState, useRef } from 'react'
import { api } from '../services/api'
import './VisionModal.css'

function VisionModal({ onClose, sessionId }) {
  const [imagePath, setImagePath] = useState('')
  const [prompt, setPrompt] = useState('请详细描述这张图片的内容，用中文回答。')
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState('')
  const [uploadedFile, setUploadedFile] = useState(null)
  const [uploadedPath, setUploadedPath] = useState('')
  const fileInputRef = useRef(null)

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    setUploadedFile(file)
    const formData = new FormData()
    formData.append('file', file)
    if (sessionId) formData.append('session_id', sessionId)

    try {
      const resp = await api.post('/vision/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      if (resp.data.success) {
        setUploadedPath(resp.data.saved_as)
        setImagePath(resp.data.saved_as)
        alert(`✅ 已上传: ${resp.data.filename}`)
      } else {
        alert(`上传失败: ${resp.data.error || '未知错误'}`)
      }
    } catch (err) {
      alert(`上传失败: ${err.message}`)
    }
  }

  const handleAnalyze = async () => {
    if (!imagePath.trim()) {
      alert('请先上传图片或输入图片路径')
      return
    }

    setIsLoading(true)
    setResult('')

    try {
      const resp = await api.post('/vision/analyze', {
        image_path: imagePath,
        prompt: prompt || '请详细描述这张图片的内容，用中文回答。',
        session_id: sessionId,
      })

      if (resp.data.success) {
        setResult(resp.data.result)
      } else {
        setResult(`❌ 分析失败: ${resp.data.detail || '未知错误'}`)
      }
    } catch (err) {
      setResult(`❌ 请求失败: ${err.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">🖼️ 视觉分析</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="vision-upload-area">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />
            <button
              className="vision-upload-btn"
              onClick={() => fileInputRef.current?.click()}
            >
              📤 上传图片
            </button>
            {uploadedFile && (
              <span className="vision-upload-name">{uploadedFile.name}</span>
            )}
          </div>

          <div className="vision-path-input">
            <label>图片路径</label>
            <input
              type="text"
              value={imagePath}
              onChange={(e) => setImagePath(e.target.value)}
              placeholder="test.png"
            />
          </div>

          <div className="vision-prompt-input">
            <label>分析提示</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={2}
              placeholder="请详细描述这张图片的内容，用中文回答。"
            />
          </div>

          <button
            className="vision-analyze-btn"
            onClick={handleAnalyze}
            disabled={isLoading}
          >
            {isLoading ? '分析中...' : '🔍 分析图片'}
          </button>

          {isLoading && (
            <div className="vision-loading">
              <div className="vision-loading-spinner" />
              <span>正在分析图片...</span>
            </div>
          )}

          {result && (
            <div className="vision-result">
              <div className="vision-result-title">📝 结果</div>
              <div className="vision-result-content">{result}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default VisionModal