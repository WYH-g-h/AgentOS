# skills/registry.py
"""
技能注册表：管理所有技能
"""

from typing import Dict, Optional, List, Callable, Any

from core.registry import Registry
from .base import SkillSpec


class SkillRegistry(Registry[SkillSpec]):
    """技能注册表"""

    def __init__(self):
        super().__init__("skills")
        self._handlers: Dict[str, Callable] = {}

    def register_skill(self, spec: SkillSpec, handler: Callable):
        """注册技能"""
        self.register(spec.name, spec)
        self._handlers[spec.name] = handler

    def get_handler(self, name: str) -> Optional[Callable]:
        """获取技能处理器"""
        return self._handlers.get(name)

    def reload(self):
        """重新加载所有技能（兼容 admin.py 调用）"""
        from .loader import load_skills
        import os
        # 尝试从当前目录或打包目录加载
        skills_dir = os.path.join(os.path.dirname(__file__), '..', 'skills')
        if not os.path.exists(skills_dir):
            skills_dir = './skills'
        load_skills(skills_dir)

    def match(self, user_input: str) -> Optional[str]:
        """根据用户输入匹配技能 - 使用独立词匹配"""
        user_input = user_input.strip()
        import re

        candidates = []
        for name, spec in self._items.items():
            if not spec.enabled:
                continue
            for trigger in spec.triggers:
                pattern = r'(^|[\s，,。.、；;：:！!？?])({})(?=[\s，,。.、；;：:！!？?]|$)'.format(re.escape(trigger))
                if re.search(pattern, user_input):
                    candidates.append((len(trigger), name))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        return None

    def list_enabled(self) -> List[SkillSpec]:
        """列出启用的技能"""
        return [s for s in self.list_all() if s.enabled]

    def match_exact(self, user_input: str) -> Optional[str]:
        """根据用户输入匹配技能 - 使用精确独立词匹配"""
        user_input = user_input.strip()
        import re

        candidates = []
        for name, spec in self._items.items():
            if not spec.enabled:
                continue
            for trigger in spec.triggers:
                pattern = r'(^|[\s，,。.、；;：:！!？?])({})(?=[\s，,。.、；;：:！!？?]|$)'.format(re.escape(trigger))
                if re.search(pattern, user_input):
                    candidates.append((len(trigger), name))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        return self.match(user_input)


# 全局技能注册表
skill_registry = SkillRegistry()