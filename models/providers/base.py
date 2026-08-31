# models/providers/base.py
"""
模型提供者基类
"""

from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """模型提供者基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._available = True

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """对话接口"""
        pass

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """向量化接口"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查是否可用"""
        pass

    @abstractmethod
    def get_model_names(self) -> Dict[str, str]:
        """获取模型名称映射 {role: model_name}"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供者名称"""
        pass

    def close(self):
        """关闭连接（可选）"""
        pass