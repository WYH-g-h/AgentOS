# core/interfaces.py
"""
扩展接口定义 - 所有可插拔组件的抽象接口
v4 预留接口
"""

from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod


class ModelProviderInterface(ABC):
    """模型提供者扩展接口"""

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

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供者名称"""
        pass


class StorageInterface(ABC):
    """存储后端扩展接口"""

    @abstractmethod
    def save(self, key: str, value: Any) -> bool:
        """保存数据"""
        pass

    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        """加载数据"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除数据"""
        pass

    @abstractmethod
    def list_keys(self, prefix: str = "") -> List[str]:
        """列出所有键"""
        pass


class ToolInterface(ABC):
    """工具扩展接口"""

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """执行工具"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    @property
    def input_schema(self) -> Optional[Dict]:
        """输入参数规范（可选）"""
        return None

    @property
    def output_schema(self) -> Optional[Dict]:
        """输出格式规范（可选）"""
        return None


class SkillInterface(ABC):
    """技能扩展接口"""

    @abstractmethod
    def execute(self, context) -> str:
        """执行技能"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """技能名称"""
        pass


class WorkflowInterface(ABC):
    """工作流扩展接口"""

    @abstractmethod
    def execute(self, context) -> str:
        """执行工作流"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """工作流名称"""
        pass


class PluginInterface(ABC):
    """v4: 插件接口 - 支持第三方扩展"""

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        pass

    @abstractmethod
    def execute(self, context: Any) -> Any:
        """执行插件"""
        pass

    @abstractmethod
    def shutdown(self) -> bool:
        """关闭插件"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass


class MarketInterface(ABC):
    """v4: 技能市场接口"""

    @abstractmethod
    def list_available(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出可下载的技能/工作流"""
        pass

    @abstractmethod
    def download(self, package_id: str) -> bool:
        """下载技能/工作流"""
        pass

    @abstractmethod
    def upload(self, package_path: str) -> bool:
        """上传技能/工作流"""
        pass


class SyncInterface(ABC):
    """v4: 云端同步接口"""

    @abstractmethod
    def sync(self, direction: str = "both") -> bool:
        """同步数据"""
        pass

    @abstractmethod
    def get_remote_status(self) -> Dict[str, Any]:
        """获取远程状态"""
        pass