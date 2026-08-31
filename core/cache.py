# core/cache.py
"""
统一缓存系统：LRU + TTL
"""

import time
import threading
import hashlib
import json
from typing import Any, Optional, Dict, Callable
from collections import OrderedDict
from functools import wraps

from .logger import agent_logger


def _make_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """✅ 生成安全的缓存键"""
    try:
        key_data = {
            "func": func_name,
            "args": [str(a) for a in args],
            "kwargs": {k: str(v) for k, v in kwargs.items()}
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    except Exception:
        # 降级方案
        return f"{func_name}:{str(args)}:{str(kwargs)}"


class Cache:
    """通用缓存（LRU + TTL）"""

    def __init__(self, max_size: int = 100, ttl: int = 3600, name: str = "default"):
        """
        Args:
            max_size: 最大缓存条目数
            ttl: 过期时间（秒），0 表示永不过期
            name: 缓存名称（用于日志）
        """
        self.max_size = max_size
        self.ttl = ttl
        self.name = name
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.RLock()
        self._hit_count = 0
        self._miss_count = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            if key not in self._cache:
                self._miss_count += 1
                return None

            value, timestamp = self._cache[key]

            # 检查是否过期
            if self.ttl > 0 and time.time() - timestamp > self.ttl:
                del self._cache[key]
                self._miss_count += 1
                return None

            # 移到末尾（LRU）
            self._cache.move_to_end(key)
            self._hit_count += 1
            return value

    def set(self, key: str, value: Any):
        """设置缓存"""
        with self._lock:
            if len(self._cache) >= self.max_size:
                # 移除最旧的（LRU）
                oldest_key, _ = self._cache.popitem(last=False)
                agent_logger.debug(f"缓存 {self.name} 淘汰: {oldest_key}")

            self._cache[key] = (value, time.time())

    def get_or_set(self, key: str, func: Callable, *args, **kwargs) -> Any:
        """获取缓存，如果不存在则调用函数设置"""
        value = self.get(key)
        if value is not None:
            return value

        value = func(*args, **kwargs)
        self.set(key, value)
        return value

    def remove(self, key: str) -> bool:
        """移除缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            agent_logger.info(f"缓存 {self.name} 已清空")

    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._hit_count + self._miss_count
        return {
            "name": self.name,
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl": self.ttl,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": self._hit_count / total if total > 0 else 0,
        }


# ============================================================
# 预定义缓存实例
# ============================================================

memory_cache = Cache(max_size=50, ttl=600, name="memory")
rag_cache = Cache(max_size=30, ttl=300, name="rag")
model_cache = Cache(max_size=20, ttl=3600, name="model")
file_cache = Cache(max_size=10, ttl=30, name="file")


def cached(ttl: int = 3600, cache_instance: Cache = None):
    """
    装饰器：自动缓存函数返回值
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = cache_instance or model_cache
            key = _make_cache_key(func.__name__, args, kwargs)

            result = cache.get(key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        return wrapper

    return decorator