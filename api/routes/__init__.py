# api/routes/__init__.py
"""API 路由模块"""

from . import chat, tools, skills, workflows, memory, rag, vision, health, admin

__all__ = [
    "chat",
    "tools",
    "skills",
    "workflows",
    "memory",
    "rag",
    "vision",
    "health",
    "admin",
]