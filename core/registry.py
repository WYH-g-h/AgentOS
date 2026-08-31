# core/registry.py
"""
注册表基类：所有注册表的通用实现
"""

from typing import Dict, Optional, List, Generic, TypeVar, Any

T = TypeVar('T')


class Registry(Generic[T]):
    """通用注册表基类"""

    def __init__(self, name: str = "registry"):
        self.name = name
        self._items: Dict[str, T] = {}

    def register(self, name: str, item: T):
        """注册项"""
        self._items[name] = item

    def get(self, name: str) -> Optional[T]:
        """获取项"""
        return self._items.get(name)

    def list_all(self) -> List[T]:
        """列出所有项"""
        return list(self._items.values())

    def list_names(self) -> List[str]:
        """列出所有名称"""
        return list(self._items.keys())

    def remove(self, name: str) -> bool:
        """移除项"""
        if name in self._items:
            del self._items[name]
            return True
        return False

    def clear(self):
        """清空所有"""
        self._items.clear()

    def count(self) -> int:
        """数量"""
        return len(self._items)

    def exists(self, name: str) -> bool:
        """是否存在"""
        return name in self._items