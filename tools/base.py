# tools/base.py
"""
工具基类：定义工具接口
"""

from typing import Any, Dict, Callable, Optional
from dataclasses import dataclass


@dataclass
class ToolSpec:
    """工具规格"""
    name: str
    description: str
    func: Callable
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class BaseTool:
    """工具基类"""

    name: str = None
    description: str = None

    def execute(self, **kwargs) -> Any:
        """执行工具"""
        raise NotImplementedError