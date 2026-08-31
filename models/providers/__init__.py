# models/providers/__init__.py
"""
模型提供者：支持不同后端
"""

from .base import BaseProvider
from .ollama import OllamaProvider

# 🆕 新提供者（可选导入，如果依赖未安装则跳过）
try:
    from .openai import OpenAIProvider
except ImportError:
    OpenAIProvider = None

try:
    from .deepseek import DeepSeekProvider
except ImportError:
    DeepSeekProvider = None

__all__ = [
    "BaseProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "DeepSeekProvider",
]