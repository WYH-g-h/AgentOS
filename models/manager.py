# models/manager.py
"""
模型管理器：管理模型实例，支持缓存和健康检查
使用工厂模式支持多提供商
"""

from typing import Optional, Dict, Any, Tuple, Union
from langchain_ollama import ChatOllama

from .registry import ModelSpec, model_registry, ModelCapability
from core.health import health_check
from core.config import config
from core.factory import model_factory
from core.logger import agent_logger
from models.providers.ollama import OllamaProvider  # ✅ 添加导入


class ModelManager:
    """模型管理器 - 单例"""

    _instance = None
    _instances: Dict[str, Any] = {}
    _provider_cache: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_model(self, name: str, provider: str = None, **kwargs) -> Optional[Any]:
        """
        获取模型实例（带缓存）

        Args:
            name: 模型名称
            provider: 提供者名称 (ollama, openai, deepseek)
            **kwargs: 额外参数

        Returns:
            模型实例
        """
        # 构建缓存键
        provider_key = provider or "ollama"
        cache_key = f"{provider_key}:{name}"

        if cache_key in self._instances:
            return self._instances[cache_key]

        # 如果指定了非ollama提供者，使用工厂
        if provider and provider != "ollama":
            providers_config = config.get("providers", {})
            provider_config = providers_config.get(provider, {})

            if not provider_config.get("enabled", False):
                agent_logger.warning(f"提供者 {provider} 未启用")
                return None

            provider_instance = model_factory.create(provider, provider_config)
            if provider_instance and provider_instance.is_available():
                self._instances[cache_key] = provider_instance
                return provider_instance

            return None

        # ✅ 修复：视觉模型使用 OllamaProvider（有 vision 方法）
        vision_models = ["llava:7b", "bakllava:7b", "llava:13b", "cogvlm", "qwen-vl"]
        if name in vision_models:
            provider_config = {
                "base_url": config.get("ollama.base_url", "http://localhost:11434"),
                "models": {
                    "vision": name,
                    "thinker": config.get("models.thinker", "deepseek-r1:8b"),
                    "doer": config.get("models.doer", "qwen3.5:9b"),
                    "router": config.get("models.router", "qwen2.5:3b"),
                    "embedding": config.get("models.embedding", "nomic-embed-text:latest"),
                }
            }
            provider_instance = OllamaProvider(provider_config)
            if provider_instance.is_available():
                self._instances[cache_key] = provider_instance
                agent_logger.debug(f"✅ 创建视觉模型实例: {name}")
                return provider_instance
            return None

        # 默认使用 Ollama
        spec = model_registry.get(name)
        if not spec:
            return None

        # 从配置获取参数
        base_url = kwargs.get("base_url") or config.get("ollama.base_url", "http://localhost:11434")
        temperature = kwargs.get("temperature", spec.temperature)
        timeout = kwargs.get("timeout", spec.timeout)
        num_predict = kwargs.get("num_predict", spec.num_predict)

        # 从配置读取额外参数
        models_config = config.get("models", {})
        model_config = models_config.get(name, {})
        if model_config:
            temperature = model_config.get("temperature", temperature)

        model = ChatOllama(
            model=spec.name,
            base_url=base_url,
            temperature=temperature,
            timeout=timeout,
            num_predict=num_predict,
        )

        self._instances[cache_key] = model
        return model

    def get_model_by_config(self, model_name: str, provider: str = None) -> Optional[Any]:
        """
        根据配置名获取模型（用于技能配置）

        Args:
            model_name: 模型名称或角色名 (thinker, doer, router, embedding)
            provider: 提供者名称
        """
        if not model_name:
            return None

        # 检查是否是角色名
        role_map = {
            "thinker": self.get_thinker,
            "doer": self.get_doer,
            "router": self.get_router,
            "embedding": self.get_embedding,
        }

        if model_name in role_map:
            return role_map[model_name]()

        # 尝试直接获取
        return self.get_model(model_name, provider)

    def _get_model_by_role(self, role: str, provider: str = None) -> Optional[Any]:
        """根据角色获取模型"""
        if provider and provider != "ollama":
            provider_instance = self._get_provider_instance(provider)
            if provider_instance:
                return provider_instance

        if role == "thinker":
            spec = model_registry.get_thinker()
        elif role == "doer":
            spec = model_registry.get_doer()
        elif role == "router":
            spec = model_registry.get_router()
        elif role == "embedding":
            spec = model_registry.get_embedding()
        else:
            return None

        if spec:
            return self.get_model(spec.name)
        return None

    def _get_provider_instance(self, provider: str) -> Optional[Any]:
        """获取提供者实例"""
        if provider in self._provider_cache:
            return self._provider_cache[provider]

        providers_config = config.get("providers", {})
        provider_config = providers_config.get(provider, {})

        if not provider_config.get("enabled", False):
            return None

        instance = model_factory.create(provider, provider_config)
        if instance and instance.is_available():
            self._provider_cache[provider] = instance
            return instance

        return None

    def get_thinker(self, provider: str = None) -> Optional[Any]:
        """获取思考模型"""
        if provider:
            return self._get_provider_instance(provider)
        return self._get_model_by_role("thinker")

    def get_doer(self, provider: str = None) -> Optional[Any]:
        """获取执行模型"""
        if provider:
            return self._get_provider_instance(provider)
        return self._get_model_by_role("doer")

    def get_router(self, provider: str = None) -> Optional[Any]:
        """获取路由模型"""
        if provider:
            return self._get_provider_instance(provider)
        return self._get_model_by_role("router")

    def get_embedding(self, provider: str = None) -> Optional[Any]:
        """获取向量模型"""
        if provider:
            instance = self._get_provider_instance(provider)
            if instance and hasattr(instance, 'embed'):
                return instance
        return self._get_model_by_role("embedding")

    def clear_cache(self):
        """清空模型缓存"""
        self._instances.clear()
        self._provider_cache.clear()
        agent_logger.debug("模型缓存已清空")

    def safe_invoke(self, model, prompt: str, **kwargs) -> Tuple[Optional[str], Optional[str]]:
        """
        安全调用模型（使用 health_check.safe_call）
        返回: (response, error)
        """

        def invoke_func():
            if hasattr(model, 'invoke'):
                return model.invoke(prompt, **kwargs)
            elif hasattr(model, 'chat'):
                messages = [{"role": "user", "content": prompt}]
                return model.chat(messages, **kwargs)
            else:
                return model(prompt, **kwargs)

        result, error = health_check.safe_call(invoke_func, max_retries=3)

        if error:
            return None, error

        if result:
            if hasattr(result, 'content'):
                return result.content, None
            return str(result), None
        return None, "❌ 推理返回空结果"


# 全局管理器实例
model_manager = ModelManager()