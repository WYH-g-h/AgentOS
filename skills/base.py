# skills/base.py
"""
技能基类：定义技能接口
增强: 提示词与技能捆绑
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class SkillSpec:
    """技能规格 - 增强提示词支持"""
    name: str
    description: str
    version: str = "1.0"
    category: str = "general"

    # 依赖的工具
    tools: List[str] = field(default_factory=list)

    # 执行配置
    model: Optional[str] = None
    timeout: int = 60
    retries: int = 2

    # 触发关键词
    triggers: List[str] = field(default_factory=list)

    # 是否启用
    enabled: bool = True

    # 路径
    path: Optional[str] = None

    # 提示词配置
    prompt: Dict[str, Any] = field(default_factory=dict)
    prompt_vars: Dict[str, str] = field(default_factory=dict)


class BaseSkill:
    """技能基类"""

    spec: SkillSpec = None

    def execute(self, context) -> str:
        """执行技能"""
        raise NotImplementedError