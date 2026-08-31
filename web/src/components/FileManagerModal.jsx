// web/src/components/FileManagerModal.jsx
import React, { useState, useEffect } from 'react'
import { AgentAPI } from '../services/api'
import './FileManagerModal.css'

function FileManagerModal({ onClose }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadFiles()
  }, [])

  const loadFiles = async () => {
    try {
      const resp = await AgentAPI.adminListOutputFiles()
      setFiles(resp.data?.files || [])
    } catch (e) {
      console.error('加载文件失败:', e)
    } finally {
      setLoading(false)
    }
  }

  const deleteFile = async (filename) => {
    if (!confirm(`确定删除 ${filename} 吗？`)) return
    try {
      await AgentAPI.adminDeleteOutputFile(filename)
      loadFiles()
    } catch (e) {
      alert('删除失败: ' + e.message)
    }
  }

  const clearAll = async () => {
    if (!confirm('确定清空所有文件吗？')) return
    try {
      await AgentAPI.adminClearOutput()
      loadFiles()
    } catch (e) {
      alert('清空失败: ' + e.message)
    }
  }

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  }

  const formatDate = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleString()
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content file-manager-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">📂 产物管理</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="file-manager-actions">
            <button className="btn-refresh" onClick={loadFiles}>🔄 刷新</button>
            <button className="btn-danger" onClick={clearAll}>🗑️ 清空所有</button>
            <span className="file-count">共 {files.length} 个文件</span>
          </div>

          {loading ? (
            <div className="loading-text">加载中...</div>
          ) : files.length === 0 ? (
            <div className="empty-state">📭 暂无输出文件</div>
          ) : (
            <div className="file-list">
              {files.map((f) => (
                <div key={f.name} className="file-item">
                  <div className="file-info">
                    <span className="file-icon">📄</span>
                    <span className="file-name">{f.name}</span>
                    <span className="file-size">{formatSize(f.size)}</span>
                    <span className="file-time">{formatDate(f.modified)}</span>
                  </div>
                  <button
                    className="btn-delete-sm"
                    onClick={() => deleteFile(f.name)}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default FileManagerModal