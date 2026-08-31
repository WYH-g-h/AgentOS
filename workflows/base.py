# workflows/base.py
"""
工作流基类：定义工作流接口
增强: 提示词与模型配置
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class WorkflowStep:
    """工作流步骤"""
    name: str
    skill: str
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    condition: Optional[str] = None


@dataclass
class WorkflowSpec:
    """工作流规格 - 增强提示词和模型配置"""
    name: str
    description: str
    steps: List[WorkflowStep]
    version: str = "1.0"
    enabled: bool = True
    triggers: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None

    # 提示词配置
    prompt: Dict[str, Any] = field(default_factory=dict)
    prompt_vars: Dict[str, str] = field(default_factory=dict)

    # 模型配置
    model: Optional[str] = None
    model_config: Dict[str, Any] = field(default_factory=dict)


class BaseWorkflow:
    """工作流基类"""

    spec: WorkflowSpec = None

    def execute(self, context) -> str:
        """执行工作流"""
        raise NotImplementedError