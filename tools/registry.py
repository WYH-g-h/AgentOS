# tools/registry.py
"""
工具注册表：管理所有工具
"""

from typing import Dict, Optional, Callable, List, Any

from core.registry import Registry
from .base import ToolSpec


class ToolRegistry(Registry[ToolSpec]):
    """工具注册表"""

    def __init__(self):
        super().__init__("tools")

    def register_tool(self, name: str, func: Callable, description: str, **kwargs):
        """注册工具"""
        spec = ToolSpec(
            name=name,
            description=description,
            func=func,
            input_schema=kwargs.get("input_schema"),
            output_schema=kwargs.get("output_schema"),
        )
        self.register(name, spec)

    def execute(self, name: str, **kwargs) -> Any:
        """执行工具"""
        spec = self.get(name)
        if spec:
            return spec.func(**kwargs)
        return f"❌ 工具 {name} 不存在"

    def list_descriptions(self) -> str:
        """列出所有工具的描述"""
        lines = ["🔧 可用工具:"]
        for spec in self.list_all():
            lines.append(f"  📌 {spec.name}: {spec.description}")
        return "\n".join(lines)


# 全局工具注册表
tool_registry = ToolRegistry()