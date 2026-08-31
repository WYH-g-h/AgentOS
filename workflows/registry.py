# workflows/registry.py
"""
工作流注册表：管理所有工作流
"""

from typing import Optional, List

from core.registry import Registry
from .base import WorkflowSpec


class WorkflowRegistry(Registry[WorkflowSpec]):
    """工作流注册表"""

    def __init__(self):
        super().__init__("workflows")

    def match(self, user_input: str) -> Optional[str]:
        """根据用户输入匹配工作流"""
        user_lower = user_input.lower()

        for name, spec in self._items.items():
            if not spec.enabled:
                continue
            for trigger in spec.triggers:
                if trigger in user_lower:
                    return name

        return None

    def list_enabled(self) -> List[WorkflowSpec]:
        """列出启用的工作流"""
        return [s for s in self.list_all() if s.enabled]


# 全局工作流注册表
workflow_registry = WorkflowRegistry()