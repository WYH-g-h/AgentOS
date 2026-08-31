// web/src/components/settings/FileManager.jsx
import React, { useState, useEffect } from 'react'
import { AgentAPI } from '../../services/api'

function FileManager() {
  const [dataFiles, setDataFiles] = useState([])
  const [outputFiles, setOutputFiles] = useState([])
  const [paths, setPaths] = useState({ data_dir: '', output_dir: '' })
  const [loading, setLoading] = useState(true)
  const [newPath, setNewPath] = useState({ data_dir: '', output_dir: '' })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [filesResp, outputResp, pathsResp] = await Promise.all([
        AgentAPI.adminListDataFiles(),
        AgentAPI.adminListOutputFiles(),
        AgentAPI.adminGetPaths(),
      ])
      setDataFiles(filesResp.data?.files || [])
      setOutputFiles(outputResp.data?.files || [])
      setPaths(pathsResp.data || { data_dir: '', output_dir: '' })
      setNewPath(pathsResp.data || { data_dir: '', output_dir: '' })
    } catch (e) {
      console.error('加载文件失败:', e)
    } finally {
      setLoading(false)
    }
  }

  const deleteOutputFile = async (filename) => {
    if (!confirm(`确定删除 ${filename} 吗？`)) return
    try {
      await AgentAPI.adminDeleteOutputFile(filename)
      loadData()
    } catch (e) {
      alert('删除失败: ' + e.message)
    }
  }

  const clearOutput = async () => {
    if (!confirm('确定清空 output 目录吗？')) return
    try {
      await AgentAPI.adminClearOutput()
      loadData()
    } catch (e) {
      alert('清空失败: ' + e.message)
    }
  }

  const updatePaths = async () => {
    try {
      await AgentAPI.adminUpdatePaths(newPath)
      alert('✅ 路径已更新，重启应用生效')
      loadData()
    } catch (e) {
      alert('更新失败: ' + e.message)
    }
  }

  if (loading) return <div className="loading">加载中...</div>

  return (
    <div className="file-manager">
      <h3>📂 文件管理</h3>

      <div className="path-config">
        <h4>📁 路径设置</h4>
        <div className="path-row">
          <label>数据目录:</label>
          <input
            type="text"
            value={newPath.data_dir}
            onChange={e => setNewPath({ ...newPath, data_dir: e.target.value })}
            placeholder="输入数据目录路径"
          />
          <span className="path-hint">当前: {paths.data_dir}</span>
        </div>
        <div className="path-row">
          <label>输出目录:</label>
          <input
            type="text"
            value={newPath.output_dir}
            onChange={e => setNewPath({ ...newPath, output_dir: e.target.value })}
            placeholder="输入输出目录路径"
          />
          <span className="path-hint">当前: {paths.output_dir}</span>
        </div>
        <button className="btn-primary" onClick={updatePaths}>更新路径</button>
        <span style={{ fontSize: 12, color: '#6c757d', marginLeft: 12 }}>⚠️ 修改后需要重启应用</span>
      </div>

      <div className="file-section">
        <h4>📤 输出文件 (output/)</h4>
        <div className="file-actions">
          <button className="btn-open" onClick={() => window.electronAPI?.openDirectory('output')}>
            📂 打开文件夹
          </button>
          <button className="btn-danger" onClick={clearOutput}>🗑️ 清空所有</button>
          <button className="btn-refresh" onClick={loadData}>🔄 刷新</button>
        </div>
        <div className="file-list">
          {outputFiles.length === 0 ? (
            <div className="empty-state">暂无输出文件</div>
          ) : (
            outputFiles.slice(0, 50).map(f => (
              <div key={f.name} className="file-item">
                <span className="file-name">📄 {f.name}</span>
                <span className="file-size">{(f.size / 1024).toFixed(1)} KB</span>
                <button className="btn-delete-sm" onClick={() => deleteOutputFile(f.name)}>
                  ✕
                </button>
              </div>
            ))
          )}
          {outputFiles.length > 50 && (
            <div className="file-more">... 还有 {outputFiles.length - 50} 个文件</div>
          )}
        </div>
      </div>

      <div className="file-section">
        <h4>💾 数据文件 (data/)</h4>
        <button className="btn-open" onClick={() => window.electronAPI?.openDirectory('data')}>
          📂 打开文件夹
        </button>
        <div className="file-list">
          {dataFiles.slice(0, 20).map(f => (
            <div key={f.path} className="file-item">
              <span className="file-name">📄 {f.path}</span>
              <span className="file-size">{(f.size / 1024).toFixed(1)} KB</span>
            </div>
          ))}
          {dataFiles.length > 20 && (
            <div className="file-more">... 还有 {dataFiles.length - 20} 个文件</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default FileManager