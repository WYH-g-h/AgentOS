# core/session.py
"""
会话管理：管理对话历史和状态
增强: 会话名指定/修改 + 自动选择最近会话 + 原子写入
"""

import os
import json
import uuid
import tempfile
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from .config import config
from .logger import agent_logger


class Session:
    """会话管理 - 支持原子写入"""

    def __init__(self, session_id: Optional[str] = None,
                 session_name: Optional[str] = None,
                 session_dir: str = "./data/chats"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # 使用传入的 session_id，或自动生成
        if session_id:
            self.session_id = session_id
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4().hex[:6]
            self.session_id = f"{timestamp}_{unique_id}"

        self.session_file = self.session_dir / f"{self.session_id}.json"

        self.messages: List[Dict[str, str]] = []
        self.state: Dict[str, Any] = {}
        self.created_at = datetime.now().isoformat()

        # 会话名称
        self._name = session_name or self.session_id[:20]

        self._load()

    @property
    def name(self) -> str:
        """获取会话名称"""
        return self._name

    @name.setter
    def name(self, value: str):
        """设置会话名称"""
        self._name = value[:50]  # 限制长度
        self.save()

    def _load(self):
        """加载会话"""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.messages = data.get("messages", [])
                    self.state = data.get("state", {})
                    self.created_at = data.get("created_at", self.created_at)
                    # ✅ 从文件读取 name，如果没有则用 session_id 截断
                    self._name = data.get("name", self.session_id[:20])
                    agent_logger.info(f"加载会话: {self.session_id} ({len(self.messages)} 条)")
            except Exception as e:
                agent_logger.error(f"加载会话失败: {e}")

    def save(self):
        """原子保存会话"""
        try:
            data = {
                "session_id": self.session_id,
                "name": self._name,
                "created_at": self.created_at,
                "updated_at": datetime.now().isoformat(),
                "messages": self.messages,
                "state": self.state,
            }

            # 原子写入：先写临时文件，再替换
            fd, temp_path = tempfile.mkstemp(
                dir=self.session_dir,
                prefix='.tmp_',
                suffix='.json'
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(temp_path, self.session_file)
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

            agent_logger.debug(f"会话已保存: {self.session_id}")

        except Exception as e:
            agent_logger.error(f"保存会话失败: {e}")

    def add_message(self, role: str, content: str):
        """添加消息"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

        # 限制消息数量
        max_history = config.get("runtime.max_history", 100)
        if len(self.messages) > max_history:
            system_msgs = [m for m in self.messages if m.get("role") == "system"]
            other_msgs = [m for m in self.messages if m.get("role") != "system"]
            if system_msgs:
                keep_count = max_history - len(system_msgs)
                self.messages = system_msgs + other_msgs[-keep_count:] if keep_count > 0 else system_msgs
            else:
                self.messages = self.messages[-max_history:]

        self.save()

    def get_messages(self, include_system: bool = True) -> List[Dict[str, str]]:
        """获取消息列表"""
        if include_system:
            return self.messages
        return [m for m in self.messages if m.get("role") != "system"]

    def get_last_n(self, n: int) -> List[Dict[str, str]]:
        """获取最近 n 条消息"""
        return self.messages[-n:] if self.messages else []

    def set_state(self, key: str, value: Any):
        """设置状态"""
        self.state[key] = value
        self.save()

    def get_state(self, key: str, default: Any = None) -> Any:
        """获取状态"""
        return self.state.get(key, default)

    def clear(self):
        """清空会话"""
        self.messages = []
        self.state = {}
        self.save()
        agent_logger.info(f"会话已清空: {self.session_id}")

    def get_context(self, max_tokens: int = 4000) -> str:
        """获取上下文摘要"""
        if not self.messages:
            return ""

        recent = self.messages[-10:]
        lines = []
        for m in recent:
            role = m.get("role", "unknown")
            content = m.get("content", "")[:200]
            lines.append(f"[{role}] {content}")

        return "\n".join(lines)


class SessionManager:
    """会话管理器 - 单例"""

    _instance = None
    _sessions: Dict[str, Session] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_or_create(self, session_id: Optional[str] = None,
                      session_name: Optional[str] = None) -> Session:
        # 如果指定了 session_id，直接获取
        if session_id:
            if session_id in self._sessions:
                return self._sessions[session_id]
            session = Session(session_id, session_name)
            self._sessions[session.session_id] = session
            return session

        # ✅ 自动选择最近会话
        sessions = self.list_sessions()
        if sessions:
            latest_id = sessions[0]
            agent_logger.info(f"📂 自动选择最近会话: {latest_id}")
            if latest_id in self._sessions:
                return self._sessions[latest_id]
            # ✅ 从文件加载会话（会读取保存的 name）
            session = Session(latest_id)  # 不传 session_name，让 _load() 从文件读取
            self._sessions[session.session_id] = session
            return session

        # 没有会话，创建新会话
        session = Session(session_name=session_name or "新会话")
        self._sessions[session.session_id] = session
        session.save()
        agent_logger.info(f"📂 创建新会话: {session.session_id}")
        return session

    def list_sessions(self) -> List[str]:
        """列出所有会话（按修改时间倒序）"""
        session_dir = Path("./data/chats")
        if not session_dir.exists():
            return []

        files = list(session_dir.glob("*.json"))
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return [f.stem for f in files]

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        session_file = Path(f"./data/chats/{session_id}.json")
        if not session_file.exists():
            return None

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    "id": session_id,
                    "name": data.get("name", session_id[:20]),
                    "message_count": len(data.get("messages", [])),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                }
        except Exception:
            return None

    def rename_session(self, session_id: str, new_name: str) -> bool:
        """重命名会话"""
        session = self.get_or_create(session_id)
        session.name = new_name
        return True

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]

        session_file = Path(f"./data/chats/{session_id}.json")
        if session_file.exists():
            session_file.unlink()
            return True
        return False


# 全局会话管理器
session_manager = SessionManager()