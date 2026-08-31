# core/health.py
"""
健康检查 + 模型可用性检查（仅查询功能）
"""

import time
import threading
import requests
from typing import Optional, List, Dict, Tuple, Any


class HealthCheck:
    """健康检查管理器 - 仅查询功能"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self._is_healthy = True
        self._last_check = 0
        self._check_interval = 30
        self._lock = threading.Lock()
        self._model_cache = {}
        self._available_models = []

    def is_healthy(self, force: bool = False) -> bool:
        """检查 Ollama 是否运行"""
        now = time.time()
        if not force and (now - self._last_check) < self._check_interval:
            return self._is_healthy

        with self._lock:
            try:
                resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
                healthy = resp.status_code == 200
                if healthy:
                    self._refresh_available_models(resp.json())
                self._is_healthy = healthy
            except Exception:
                self._is_healthy = False
            self._last_check = time.time()
        return self._is_healthy

    def _refresh_available_models(self, data: dict):
        """刷新可用模型列表"""
        models = data.get("models", [])
        self._available_models = []
        for model in models:
            name = model.get("name", "")
            if name:
                self._available_models.append({
                    "name": name,
                    "size": model.get("size", 0),
                    "modified": model.get("modified_at", ""),
                })

    def get_available_models(self, force_refresh: bool = False) -> List[Dict]:
        """获取可用模型列表"""
        if force_refresh or not self._available_models:
            self.is_healthy(force=True)
        return self._available_models

    def check_model_available(self, model_name: str) -> bool:
        """检查特定模型是否可用"""
        if not self.is_healthy():
            return False

        if model_name in self._model_cache:
            return self._model_cache[model_name]

        try:
            resp = requests.post(
                f"{self.base_url}/api/show",
                json={"name": model_name},
                timeout=10
            )
            available = resp.status_code == 200
            self._model_cache[model_name] = available
            return available
        except Exception:
            self._model_cache[model_name] = False
            return False

    def get_status_summary(self) -> Dict:
        """获取状态摘要"""
        self.is_healthy(force=True)
        return {
            "ollama_running": self._is_healthy,
            "models": self._available_models,
            "model_count": len(self._available_models),
            "base_url": self.base_url,
        }

    def reset(self):
        """重置健康状态"""
        with self._lock:
            self._is_healthy = True
            self._last_check = 0

    # ✅ 添加 safe_call 方法
    def safe_call(self, func, *args, max_retries: int = 3, **kwargs) -> Tuple[Any, Optional[str]]:
        """
        安全调用函数，带重试机制

        Args:
            func: 要调用的函数
            *args: 位置参数
            max_retries: 最大重试次数
            **kwargs: 关键字参数

        Returns:
            (result, error): 成功返回 (result, None)，失败返回 (None, error_message)
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                return result, None
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))

        return None, last_error or "调用失败"


# 全局健康检查实例
health_check = HealthCheck()