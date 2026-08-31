# models/providers/ollama.py
"""
Ollama 提供者：封装 Ollama API
"""

import requests
from typing import Optional, List, Dict, Any
import os

# ✅ 修复: 继承 BaseProvider
from .base import BaseProvider
from core.logger import agent_logger


class OllamaProvider(BaseProvider):
    """Ollama 模型提供者"""

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 配置字典，包含 base_url, models 等
        """
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.models = config.get("models", {})
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._available = True

        # 检查 Ollama 是否可用
        try:
            resp = self._session.get(f"{self.base_url}/api/tags", timeout=5)
            self._available = resp.status_code == 200
        except Exception:
            self._available = False
            agent_logger.warning(f"Ollama 服务不可用: {self.base_url}")

    @property
    def provider_name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        """检查是否可用"""
        return self._available

    def get_model_names(self) -> Dict[str, str]:
        """获取模型名称映射"""
        return {
            "thinker": self.models.get("thinker", "deepseek-r1:8b"),
            "doer": self.models.get("doer", "qwen3.5:9b"),
            "router": self.models.get("router", "qwen2.5:3b"),
            "embedding": self.models.get("embedding", "nomic-embed-text:latest"),
        }

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        对话接口 - 通过 Ollama API

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            **kwargs: model, temperature, timeout 等

        Returns:
            str: 响应内容
        """
        if not self.is_available():
            return "❌ Ollama 服务不可用"

        try:
            model = kwargs.get("model", "qwen3.5:9b")
            temperature = kwargs.get("temperature", 0.2)
            timeout = kwargs.get("timeout", 120)

            # 构建请求
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": kwargs.get("num_predict", 4096),
                }
            }

            resp = self._session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=timeout
            )

            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "")
            else:
                error_msg = resp.text
                agent_logger.error(f"Ollama chat 失败: {resp.status_code} - {error_msg}")
                return f"❌ Ollama 调用失败: {resp.status_code}"

        except requests.Timeout:
            return "❌ Ollama 调用超时"
        except Exception as e:
            agent_logger.error(f"Ollama chat 异常: {e}")
            return f"❌ Ollama 调用异常: {e}"

    def vision(self, image_path: str, prompt: str, **kwargs) -> str:
        """
        视觉模型调用 - 分析图片

        Args:
            image_path: 图片路径
            prompt: 用户提示词

        Returns:
            str: 模型响应
        """
        if not self.is_available():
            return "❌ Ollama 服务不可用"

        try:
            import base64

            # 检查图片是否存在
            if not os.path.exists(image_path):
                return f"❌ 图片不存在: {image_path}"

            # 读取图片并编码为 base64
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            # 检测文件类型
            ext = image_path.split('.')[-1].lower()
            media_type = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'webp': 'image/webp',
                'bmp': 'image/bmp',
                'svg': 'image/svg+xml',
            }.get(ext, 'image/png')

            model = kwargs.get("model", "llava:7b")
            temperature = kwargs.get("temperature", 0.2)
            num_predict = kwargs.get("num_predict", 2048)

            # Ollama 视觉 API
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_data]
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": num_predict,
                }
            }

            resp = self._session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=kwargs.get("timeout", 120)
            )

            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "")
            else:
                error_msg = resp.text
                agent_logger.error(f"视觉模型调用失败: {resp.status_code} - {error_msg}")
                return f"❌ 视觉模型调用失败: {resp.status_code}"

        except FileNotFoundError:
            return f"❌ 图片不存在: {image_path}"
        except Exception as e:
            agent_logger.error(f"视觉模型调用异常: {e}")
            return f"❌ 视觉模型调用异常: {e}"

    def embed(self, text: str) -> List[float]:
        """向量化接口 - 通过 Ollama Embeddings API"""
        if not self.is_available():
            return []

        try:
            model = self.models.get("embedding", "nomic-embed-text:latest")

            payload = {
                "model": model,
                "prompt": text,
            }

            resp = self._session.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
                timeout=30
            )

            if resp.status_code == 200:
                data = resp.json()
                return data.get("embedding", [])
            else:
                agent_logger.error(f"Ollama embed 失败: {resp.status_code}")
                return []

        except Exception as e:
            agent_logger.error(f"Ollama embed 异常: {e}")
            return []

    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有可用模型"""
        try:
            resp = self._session.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("models", [])
        except Exception as e:
            agent_logger.warning(f"获取模型列表失败: {e}")
        return []

    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """获取模型信息"""
        try:
            resp = self._session.post(
                f"{self.base_url}/api/show",
                json={"name": model_name},
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            agent_logger.warning(f"获取模型信息失败: {e}")
        return None

    def is_running(self) -> bool:
        """检查 Ollama 是否运行"""
        try:
            resp = self._session.get(f"{self.base_url}/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def close(self):
        """关闭会话"""
        if self._session:
            self._session.close()
            self._session = None

    def stream(self, prompt: str, **kwargs):
        """流式对话接口"""
        if not self.is_available():
            yield "❌ Ollama 服务不可用"
            return

        try:
            model = kwargs.get("model", "qwen3.5:9b")
            temperature = kwargs.get("temperature", 0.2)
            timeout = kwargs.get("timeout", 120)

            # 构建消息
            messages = [{"role": "user", "content": prompt}]

            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": kwargs.get("num_predict", 4096),
                }
            }

            # 流式请求
            import json
            response = self._session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=timeout
            )

            if response.status_code != 200:
                yield f"❌ Ollama 流式调用失败: {response.status_code}"
                return

            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if 'message' in data and 'content' in data['message']:
                            yield data['message']['content']
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        agent_logger.warning(f"流式解析异常: {e}")
                        continue

        except requests.Timeout:
            yield "❌ Ollama 调用超时"
        except Exception as e:
            agent_logger.error(f"Ollama 流式异常: {e}")
            yield f"❌ Ollama 调用异常: {e}"