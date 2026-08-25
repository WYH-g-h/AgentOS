# 🤖 AgentOS

> 基于认知架构的 AI 智能助手桌面应用

[![Version](https://img.shields.io/badge/version-17.0.0-blue.svg)](https://github.com/yourname/AgentOS/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)]()

---

## 📖 简介

AgentOS 是一个基于 **5层认知架构** 的 AI 智能助手桌面应用，实现了 **Tools → Skills → Workflows** 三层递进式能力体系。

用户可以通过自然语言或特殊命令，调用丰富的工具、技能和工作流，完成文件分析、代码生成、数据整理等各种任务。

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 **5层认知架构** | 感知 → 记忆 → 推理 → 执行 → 反馈 |
| 🔧 **三层能力体系** | Tools（工具）→ Skills（技能）→ Workflows（工作流）|
| 🎯 **显式路由** | 支持 `[工具]`、`【技能】`、`(工作流)` 特殊触发 |
| 🤖 **多模型协作** | Thinker / Doer / Router / Embedding 各司其职 |
| 📚 **统一知识库** | 记忆 + RAG + 规则引擎 |
| 🔌 **模型可插拔** | 支持 Ollama / OpenAI / DeepSeek |
| ⚙️ **配置驱动** | YAML 配置，支持热加载 |
| 🖥️ **桌面应用** | Electron 打包，双击即用 |

---

## 🚀 快速开始

### 系统要求

- Windows 10/11 (64位)
- 8GB 以上内存（推荐）
- 10GB 以上可用硬盘空间

### 安装步骤

#### 1. 下载 AgentOS

从 [Releases](https://github.com/yourname/AgentOS/releases) 下载最新版本的 `AgentOS-win32-x64.zip`

解压到任意文件夹。

#### 2. 安装 Ollama

AgentOS 需要 Ollama 来运行 AI 模型。

```bash
# 下载 Ollama
https://ollama.com/download/windows

# 启动 Ollama
ollama serve

# 下载模型（至少一个）
ollama pull qwen2.5:3b      # 推荐，中文效果好
ollama pull llama3.2:3b     # 英文效果好
ollama pull llava:7b        # 支持图像识别
