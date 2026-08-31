# core/factory.py
"""
模型工厂 - 实现多提供商可插拔
使用延迟导入 + 路径注册，彻底避免循环导入
"""

from typing import Dict, Optional, Any, Type
from core.interfaces import ModelProviderInterface
from core.logger import agent_logger


class ModelFactory:
    """模型工厂 - 单例模式"""

    _instance = None
    _providers: Dict[str, Type[ModelProviderInterface]] = {}
    _instances: Dict[str, ModelProviderInterface] = {}
    _provider_paths: Dict[str, str] = {}  # 🆕 存储提供者路径

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        # ✅ 只注册路径，不导入类
        self._register_provider_paths()
        agent_logger.debug("✅ 模型提供者路径已注册")

    def _register_provider_paths(self):
        """注册提供者路径（不实际导入，避免循环）"""
        self._provider_paths = {
            "ollama": "models.providers.ollama.OllamaProvider",
            "openai": "models.providers.openai.OpenAIProvider",
            "deepseek": "models.providers.deepseek.DeepSeekProvider",
        }
        # 在 _providers 中占位
        for name in self._provider_paths:
            self._providers[name] = None

    def _get_provider_class(self, provider: str) -> Optional[Type[ModelProviderInterface]]:
        """
        ✅ 延迟加载提供者类
        只有在实际使用时才导入，避免循环导入
        """
        provider_key = provider.lower()

        # 如果已经加载过，直接返回
        if self._providers.get(provider_key) is not None:
            return self._providers[provider_key]

        # 获取提供者路径
        provider_path = self._provider_paths.get(provider_key)
        if not provider_path:
            return None

        # 动态导入
        try:
            import importlib
            module_path, class_name = provider_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            provider_class = getattr(module, class_name)

            # 缓存
            self._providers[provider_key] = provider_class
            agent_logger.debug(f"✅ 加载提供者: {provider}")
            return provider_class

        except ImportError as e:
            agent_logger.warning(f"⚠️ 提供者 {provider} 未安装: {e}")
            return None
        except Exception as e:
            agent_logger.warning(f"⚠️ 提供者 {provider} 加载失败: {e}")
            return None

    def register(self, name: str, provider_class: Type[ModelProviderInterface]):
        """注册提供者（外部注册用）"""
        self._providers[name.lower()] = provider_class
        agent_logger.debug(f"注册模型提供者: {name}")

    def create(self, provider: str, config: Dict[str, Any]) -> Optional[ModelProviderInterface]:
        """
        创建模型实例

        Args:
            provider: 提供者名称 (ollama, openai, deepseek, etc.)
            config: 提供者配置

        Returns:
            ModelProviderInterface: 模型实例
        """
        provider_key = provider.lower()

        # 检查是否已缓存
        cache_key = f"{provider_key}:{str(config)}"
        if cache_key in self._instances:
            return self._instances[cache_key]

        # ✅ 延迟获取提供者类
        provider_class = self._get_provider_class(provider_key)
        if not provider_class:
            agent_logger.warning(f"未知的模型提供者: {provider}")
            return None

        try:
            instance = provider_class(config)
            if instance and instance.is_available():
                self._instances[cache_key] = instance
                agent_logger.info(f"✅ 创建模型实例: {provider}")
                return instance
            else:
                agent_logger.warning(f"⚠️ 模型提供者不可用: {provider}")
                return None
        except Exception as e:
            agent_logger.error(f"❌ 创建模型提供者失败 {provider}: {e}")
            return None

    def get_provider(self, provider: str) -> Optional[Type[ModelProviderInterface]]:
        """获取提供者类（自动延迟加载）"""
        return self._get_provider_class(provider)

    def list_providers(self) -> list:
        """列出所有已注册的提供者"""
        return list(self._provider_paths.keys())

    def clear_cache(self):
        """清空实例缓存"""
        self._instances.clear()
        agent_logger.debug("模型工厂缓存已清空")


# 全局模型工厂
model_factory = ModelFactory()