# core/memory_layer.py
"""
记忆层统一接口 - 供所有层使用
增强: 对接 unified_memory 的新功能
"""

import time
import threading
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.logger import agent_logger
from core.unified_memory import unified
from core.session import session_manager
from core.rag import rag
from core.memory_decay import memory_decay


class MemoryLayer:
    """记忆层统一接口 - 对接 unified_memory 新功能"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cache = {}
        self._pending_vectorization = []
        self._lock = threading.RLock()

    # ============================================================
    # ✅ 用户画像 (对接 unified 新功能)
    # ============================================================

    def get_user_profile(self) -> Dict[str, str]:
        """获取完整用户画像"""
        return unified.get_profile()

    def get_user_info(self, key: str) -> Optional[str]:
        """获取特定用户信息"""
        profile = unified.get_profile()
        # 尝试匹配
        for display_name, value in profile.items():
            if key in display_name or display_name in key:
                return value
        return None

    def update_user_info(self, category: str, value: str) -> str:
        """更新用户信息 - 触发自动提取"""
        result = unified.add_user_info(value, category)
        # 触发向量化
        self._trigger_vectorization(f"{category}: {value}")
        return result

    def get_profile_summary(self) -> str:
        """获取用户画像摘要"""
        return unified.get_profile_summary()

    def auto_extract_and_save(self, text: str) -> str:
        """自动提取并保存用户信息"""
        return unified.auto_extract_and_save(text)

    # ============================================================
    # ✅ 经验规则 (对接 unified 新功能)
    # ============================================================

    def learn_rule(self, rule: str):
        """学习规则 - 触发向量化"""
        unified.add_rule(rule)
        self._trigger_vectorization(f"规则: {rule}")

    def learn_rule_from_feedback(self, action: str, result: str, success: bool):
        """从反馈中学习经验规则"""
        unified.learn_rule_from_feedback(action, result, success)
        self._trigger_vectorization(f"反馈: {action[:50]}")

    def get_rules(self, context: str = "") -> str:
        """获取经验规则"""
        if context:
            return unified.get_rules_by_context(context)
        return unified.get_rules_by_context("", limit=5)

    def get_rules_by_pattern(self, pattern: str) -> List[str]:
        """按模式匹配规则"""
        results = unified.search(pattern, types=["rule"], k=10)
        return [r.get("content", "") for r in results]

    # ============================================================
    # ✅ 长期记忆 (对接 unified)
    # ============================================================

    def add_memory(self, content: str, memory_type: str = "user_info",
                   category: str = None, metadata: Dict = None) -> str:
        """添加记忆 - 自动触发向量化"""
        result = unified.add(content, memory_type, category, "manual", metadata)
        self._trigger_vectorization(content)
        return result

    def search_memory(self, query: str, types: List[str] = None, k: int = 5) -> List[Dict]:
        """搜索长期记忆"""
        return unified.search(query, types, k=k)

    def search_memory_text(self, query: str, types: List[str] = None, k: int = 3) -> str:
        """搜索长期记忆（返回文本）"""
        return unified.search_as_text(query, types, k)

    def get_memories_by_type(self, memory_type: str) -> List[Dict]:
        """按类型获取记忆"""
        return unified.get_by_type(memory_type)

    def get_all_memories(self) -> List[Dict]:
        """获取所有记忆"""
        return unified.get_all()

    def get_memory_status(self) -> Dict[str, Any]:
        """获取记忆状态"""
        return unified.get_stats()

    # ============================================================
    # ✅ 内部方法
    # ============================================================

    def _trigger_vectorization(self, content: str):
        """触发向量化（异步）"""
        if not content or len(content.strip()) < 10:
            return

        # 添加到待处理队列
        with self._lock:
            self._pending_vectorization.append({
                "content": content,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        # 如果队列过长，触发即时处理
        if len(self._pending_vectorization) > 10:
            threading.Thread(target=self._process_pending, daemon=True).start()

    def _process_pending(self):
        """处理待向量化的记忆"""
        with self._lock:
            pending = self._pending_vectorization.copy()
            self._pending_vectorization = []

        for item in pending:
            try:
                from core.rag import rag
                import uuid
                content = item.get("content", "")
                if content and len(content.strip()) > 10:
                    doc_id = f"mem_{uuid.uuid4().hex[:8]}"
                    rag.add("memory", {doc_id: content})
            except Exception as e:
                agent_logger.debug(f"向量化失败: {e}")

    # ============================================================
    # ✅ 会话管理 (对接 session_manager)
    # ============================================================

    def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """获取会话上下文"""
        session = session_manager.get_or_create(session_id)
        return {
            "messages": session.get_messages(),
            "state": session.state,
            "session_id": session.session_id,
            "name": session.name,
        }

    def get_recent_messages(self, session_id: str, n: int = 5) -> List[Dict]:
        """获取最近N条消息"""
        session = session_manager.get_or_create(session_id)
        return session.get_last_n(n)

    def get_conversation_history(self, session_id: str) -> str:
        """获取对话历史文本"""
        session = session_manager.get_or_create(session_id)
        return session.get_context()

    # ============================================================
    # ✅ RAG 检索 (对接 rag)
    # ============================================================

    def semantic_search(self, query: str, project: str = "default", k: int = 5) -> str:
        """语义检索（RAG）"""
        return rag.search(project, query, k)

    def semantic_ask(self, query: str, project: str = "default") -> str:
        """基于RAG回答问题"""
        return rag.ask(project, query)

    def add_to_rag(self, project: str, files: Dict[str, str]):
        """添加文件到RAG"""
        rag.add(project, files)

    def get_rag_stats(self) -> str:
        """获取RAG统计"""
        return rag.get_stats()


# 全局记忆层
memory_layer = MemoryLayer()