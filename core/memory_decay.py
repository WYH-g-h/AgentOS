# core/memory_decay.py
"""
记忆衰减机制 - 保持知识的时效性
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MemoryItem:
    """记忆条目"""
    content: str
    created_at: datetime
    last_accessed: datetime
    access_count: int = 1
    importance: float = 0.5  # 0-1, 用户标记的重要性
    metadata: Dict[str, Any] = None


class MemoryDecay:
    """记忆衰减管理器"""

    def __init__(self, half_life: int = 30, decay_threshold: float = 0.1):
        """
        Args:
            half_life: 半衰期（天）
            decay_threshold: 衰减阈值，低于此值归档
        """
        self.half_life = half_life
        self.decay_threshold = decay_threshold

    def calculate_weight(self, item: Dict[str, Any]) -> float:
        """
        计算记忆权重

        基于：
        1. 时间衰减 (指数衰减)
        2. 访问频率 (增强)
        3. 用户标记的重要性
        """
        # 解析时间
        created_at = self._parse_time(item.get("time") or item.get("created_at"))
        last_accessed = self._parse_time(item.get("last_accessed") or item.get("time"))

        if not created_at:
            return 0.5

        # 计算年龄（天）
        now = datetime.now()
        age = (now - created_at).days

        # 时间衰减: 2^(-age/half_life)
        time_weight = 2 ** (-age / self.half_life)

        # 访问频率增强: min(1.0, access_count / 10)
        access_count = item.get("access_count", 1)
        frequency_weight = min(1.0, access_count / 10)

        # 重要性权重 (0.3-1.0)
        importance = item.get("importance", 0.5)
        importance_weight = 0.3 + 0.7 * importance

        # 综合权重
        weight = time_weight * (0.5 + 0.5 * frequency_weight) * importance_weight

        return max(0.0, min(1.0, weight))

    def _parse_time(self, time_str: Optional[str]) -> Optional[datetime]:
        """解析时间字符串"""
        if not time_str:
            return None

        try:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                return datetime.fromisoformat(time_str)
            except ValueError:
                return None

    def should_archive(self, item: Dict[str, Any]) -> bool:
        """判断是否应该归档"""
        weight = self.calculate_weight(item)
        return weight < self.decay_threshold

    def should_keep(self, item: Dict[str, Any]) -> bool:
        """判断是否应该保留在活跃记忆中"""
        return not self.should_archive(item)

    def get_decay_status(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """获取衰减状态详情"""
        weight = self.calculate_weight(item)

        if weight >= 0.5:
            status = "active"
        elif weight >= self.decay_threshold:
            status = "decaying"
        else:
            status = "archived"

        return {
            "weight": weight,
            "status": status,
            "threshold": self.decay_threshold,
            "should_archive": self.should_archive(item),
        }

    def update_access(self, item: Dict[str, Any]):
        """更新访问记录"""
        item["last_accessed"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item["access_count"] = item.get("access_count", 0) + 1

    def set_importance(self, item: Dict[str, Any], importance: float):
        """设置重要性"""
        item["importance"] = max(0.0, min(1.0, importance))


# 全局记忆衰减实例
memory_decay = MemoryDecay()