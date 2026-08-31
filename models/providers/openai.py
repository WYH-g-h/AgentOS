# models/providers/openai.py
"""
OpenAI 模型提供者
"""

import os
from typing import List, Dict, Any, Optional

from .base import BaseProvider
from core.logger import agent_logger


class OpenAIProvider(BaseProvider):
    """OpenAI 提供者"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
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
                agent_logger.warning("openai 库未安装，请运行: pip install openai")
                self._available = False
            except Exception as e:
                agent_logger.warning(f"OpenAI 初始化失败: {e}")
                self._available = False

    @property
    def provider_name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return self._available and self._client is not None

    def get_model_names(self) -> Dict[str, str]:
        """获取模型名称映射"""
        return {
            "thinker": self.models.get("thinker", "gpt-4"),
            "doer": self.models.get("doer", "gpt-4-turbo"),
            "router": self.models.get("router", "gpt-3.5-turbo"),
            "embedding": self.models.get("embedding", "text-embedding-3-small"),
        }

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """对话接口"""
        if not self.is_available():
            return "❌ OpenAI 服务不可用"

        try:
            model = kwargs.get("model", "gpt-4-turbo")
            temperature = kwargs.get("temperature", 0.2)

            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                **{k: v for k, v in kwargs.items() if k not in ["model", "temperature"]}
            )

            return response.choices[0].message.content
        except Exception as e:
            agent_logger.error(f"OpenAI chat 失败: {e}")
            return f"❌ OpenAI 调用失败: {e}"

    def embed(self, text: str) -> List[float]:
        """向量化接口"""
        if not self.is_available():
            return []

        try:
            model = self.models.get("embedding", "text-embedding-3-small")
            response = self._client.embeddings.create(
                model=model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            agent_logger.error(f"OpenAI embed 失败: {e}")
            return []

    def close(self):
        if self._client:
            self._client.close()
            self._client = None