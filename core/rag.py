# core/rag.py
"""
RAG 检索系统 - FAISS 版本（无需 C++ 编译器）
使用 FAISS 原生 save_local/load_local 实现持久化
"""

import os
import shutil
from typing import Dict, Optional, List

from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.logger import agent_logger


class SimpleRAG:
    def __init__(self, persist_dir: str = "./data/rag"):
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
        self.embeddings = None
        self._stores: Dict[str, FAISS] = {}

    def _init_embeddings(self):
        if self.embeddings is None:
            self.embeddings = OllamaEmbeddings(model="nomic-embed-text:latest")
        return self.embeddings

    def _get_store_path(self, project: str) -> str:
        """获取项目存储目录路径"""
        project = project or "default"
        return os.path.join(self.persist_dir, project)

    def _get_store(self, project: str) -> Optional[FAISS]:
        """从磁盘加载 FAISS 索引"""
        project = project or "default"
        if project in self._stores:
            return self._stores[project]

        path = self._get_store_path(project)
        if os.path.exists(path) and os.path.isdir(path):
            try:
                self._init_embeddings()
                store = FAISS.load_local(
                    path,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                self._stores[project] = store
                agent_logger.debug(f"FAISS 加载成功: {project}")
                return store
            except Exception as e:
                agent_logger.warning(f"加载 FAISS 失败: {e}")
        return None

    def _save_store(self, project: str, store: FAISS):
        """保存 FAISS 索引到磁盘（使用原生 save_local）"""
        project = project or "default"
        path = self._get_store_path(project)
        try:
            os.makedirs(path, exist_ok=True)
            store.save_local(path)
            agent_logger.debug(f"FAISS 保存成功: {project}")
        except Exception as e:
            agent_logger.warning(f"保存 FAISS 失败: {e}")

    def add(self, project: str, files: dict):
        """添加文件到 RAG 知识库"""
        if not files:
            return

        project = project or "default"
        self._init_embeddings()

        texts = []
        metadatas = []

        for filepath, content in files.items():
            if not content or len(content.strip()) < 10:
                continue
            for i, chunk in enumerate(self.splitter.split_text(content)):
                texts.append(chunk)
                metadatas.append({
                    "project": project,
                    "file": filepath,
                    "chunk": i
                })

        if not texts:
            return

        existing = self._get_store(project)

        if existing:
            existing.add_texts(texts=texts, metadatas=metadatas)
            self._stores[project] = existing
        else:
            store = FAISS.from_texts(
                texts=texts,
                embedding=self.embeddings,
                metadatas=metadatas
            )
            self._stores[project] = store

        self._save_store(project, self._stores[project])
        agent_logger.info(f"FAISS 添加完成: {len(texts)} 条到 {project}")

    def search(self, project: str, query: str, k: int = 3) -> str:
        """搜索 RAG 知识库"""
        project = project or "default"
        store = self._get_store(project)
        if not store:
            return ""

        try:
            docs = store.similarity_search(query, k=k)
            if docs:
                lines = ["【相关知识】"]
                for d in docs:
                    file_name = d.metadata.get('file', 'unknown')
                    content = d.page_content[:200].replace('\n', ' ')
                    lines.append(f"[{file_name}] {content}...")
                return "\n".join(lines)
        except Exception as e:
            agent_logger.debug(f"FAISS 搜索失败: {e}")
        return ""

    def ask(self, project: str, query: str) -> str:
        """基于 RAG 知识库回答问题"""
        project = project or "default"
        docs = self.search(project, query, k=3)
        if not docs:
            return "📭 知识库中没有相关信息"

        from models.manager import model_manager
        from core.health import health_check

        doer = model_manager.get_doer()
        if not doer:
            return docs

        prompt = f"""基于以下知识回答问题：

【知识】：{docs}

【问题】：{query}

【回答】："""

        result, error = health_check.safe_call(doer.invoke, prompt, max_retries=1)
        if not error and result:
            return f"💡 {result.content.strip()}"
        return docs

    def list_projects(self) -> List[str]:
        """
        列出所有 RAG 项目
        """
        if not os.path.exists(self.persist_dir):
            return []

        projects = []
        for item in os.listdir(self.persist_dir):
            item_path = os.path.join(self.persist_dir, item)
            if os.path.isdir(item_path):
                # 检查是否是 FAISS 索引目录
                index_file = os.path.join(item_path, "index.faiss")
                if os.path.exists(index_file):
                    projects.append(item)
        return projects

    def get_stats(self) -> str:
        """获取 RAG 统计信息"""
        projects = self.list_projects()

        total_chunks = 0
        for project in projects:
            store = self._get_store(project)
            if store:
                # FAISS 没有直接获取文档数量的方法，用索引大小估算
                total_chunks += 1  # 至少有一个项目

        return f"📊 RAG统计: {len(projects)} 个项目"

    def delete_project(self, project: str) -> bool:
        """删除一个 RAG 项目"""
        project = project or "default"
        path = self._get_store_path(project)

        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                if project in self._stores:
                    del self._stores[project]
                agent_logger.info(f"删除 RAG 项目: {project}")
                return True
            except Exception as e:
                agent_logger.warning(f"删除 RAG 项目失败: {e}")
                return False
        return False


rag = SimpleRAG()