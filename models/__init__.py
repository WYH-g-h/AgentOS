# models/__init__.py
"""
模型层：模型注册、管理、自动发现
"""

from .registry import ModelCapability, ModelSpec, model_registry, ModelRegistry
from .manager import model_manager, ModelManager
from .providers.ollama import OllamaProvider
from .providers.base import BaseProvider

# 🆕 新提供者
try:
    from .providers.openai import OpenAIProvider
except ImportError:
    OpenAIProvider = None

try:
    from .providers.deepseek import DeepSeekProvider
except ImportError:
    DeepSeekProvider = None

__all__ = [
    "ModelCapability",
    "ModelSpec",
    "model_registry",
    "ModelRegistry",
    "model_manager",
    "ModelManager",
    "OllamaProvider",
    "BaseProvider",
    "OpenAIProvider",
    "DeepSeekProvider",
]