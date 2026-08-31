# models/providers/deepseek.py
"""
DeepSeek 模型提供者
"""

import os
from typing import List, Dict, Any

from .base import BaseProvider
from core.logger import agent_logger


class DeepSeekProvider(BaseProvider):
    """DeepSeek 提供者"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = config.get("base_url", "https://api.deepseek.com/v1")
        self.models = config.get("models", {})
        self._client = None
        self._available = bool(self.api_key)

        if self._available:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                agent_logger.warning("openai 库未安装 (DeepSeek需要)")
                self._available = False
            except Exception as e:
                agent_logger.warning(f"DeepSeek 初始化失败: {e}")
                self._available = False

    @property
    def provider_name(self) -> str:
        return "deepseek"

    def is_available(self) -> bool:
        return self._available and self._client is not None

    def get_model_names(self) -> Dict[str, str]:
        return {
            "thinker": self.models.get("thinker", "deepseek-chat"),
            "doer": self.models.get("doer", "deepseek-coder"),
            "router": self.models.get("router", "deepseek-chat"),
            "embedding": self.models.get("embedding", "deepseek-embedding"),
        }

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.is_available():
            return "❌ DeepSeek 服务不可用"

        try:
            model = kwargs.get("model", "deepseek-chat")
            temperature = kwargs.get("temperature", 0.2)

            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )

            return response.choices[0].message.content
        except Exception as e:
            agent_logger.error(f"DeepSeek chat 失败: {e}")
            return f"❌ DeepSeek 调用失败: {e}"

    def embed(self, text: str) -> List[float]:
        if not self.is_available():
            return []

        try:
            model = self.models.get("embedding", "deepseek-embedding")
            response = self._client.embeddings.create(
                model=model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            agent_logger.error(f"DeepSeek embed 失败: {e}")
            return []