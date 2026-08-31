# core/context.py
"""
执行上下文：贯穿整个执行过程的数据容器
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ExecutionContext:
    """执行上下文"""

    # 用户输入
    user_input: str = ""

    # 路由结果
    route_result: Dict[str, Any] = field(default_factory=dict)

    # 执行状态
    state: Dict[str, Any] = field(default_factory=dict)

    # 中间结果
    results: Dict[str, Any] = field(default_factory=dict)

    # 当前步骤
    current_step: str = ""
    current_skill: str = ""
    current_workflow: str = ""

    # 错误信息
    errors: list = field(default_factory=list)

    # 执行时间
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def set_state(self, key: str, value: Any):
        """设置状态"""
        self.state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """获取状态"""
        return self.state.get(key, default)

    def set_result(self, key: str, value: Any):
        """设置结果"""
        self.results[key] = value

    def get_result(self, key: str, default: Any = None) -> Any:
        """获取结果"""
        return self.results.get(key, default)

    def add_error(self, error: str):
        """添加错误"""
        self.errors.append(error)

    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0

    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        return {
            "user_input": self.user_input,
            "route": self.route_result,
            "state": self.state,
            "results": self.results,
            "current_step": self.current_step,
            "current_skill": self.current_skill,
            "current_workflow": self.current_workflow,
            "errors": self.errors,
        }