# core/memory_rules.py
"""
记忆规则引擎：快速匹配 + 提取
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class MemoryType:
    name: str
    keywords: list
    patterns: list
    template: str
    display_name: str = ""


class MemoryRuleEngine:
    """快速规则匹配引擎"""

    def __init__(self):
        self.types = {}
        self._load_defaults()

    def _load_defaults(self):
        # 保留所有规则，用于快速匹配
        defaults = [
            MemoryType("name", ["名字", "姓名", "叫什么", "我是"],
                       [r'(?:我的)?名字\s*[是为叫]?\s*([^\s，,。.；;]+)',
                        r'我是\s*([^\s，,。.；;]+)'],
                       "你的名字是{value}。", "名字"),
            MemoryType("age", ["年龄", "岁", "几岁", "多大"],
                       [r'(\d+)\s*岁'],
                       "你今年{value}岁。", "年龄"),
            MemoryType("birthday", ["生日", "出生"],
                       [r'(\d+月\d+日)'],
                       "你的生日是{value}。", "生日"),
            MemoryType("email", ["邮箱", "email"],
                       [r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'],
                       "你的邮箱是{value}。", "邮箱"),
            MemoryType("school", ["学校", "大学", "学院", "在读"],
                       [r'(?:在|于)?\s*([^\s，,。.；;]+(?:大学|学院|学校))'],
                       "你在{value}读书。", "学校"),
            MemoryType("hobby", ["爱好", "兴趣", "喜欢"],
                       [r'喜欢\s*([^\s，,。.；;]+)'],
                       "你的爱好是{value}。", "爱好"),
            MemoryType("password", ["密码"],
                       [r'密码\s*[是为]?\s*([^\s，,。.；;]+)'],
                       "你的{key}是{value}。", "密码"),
        ]
        for t in defaults:
            self.types[t.name] = t

    def match(self, text: str) -> Optional[MemoryType]:
        text_lower = text.lower()
        for mem_type in self.types.values():
            for kw in mem_type.keywords:
                if kw in text_lower:
                    return mem_type
        return None

    def extract_value(self, text: str, mem_type: MemoryType) -> Optional[str]:
        for pattern in mem_type.patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def extract_key(self, text: str, mem_type: MemoryType) -> str:
        match = re.search(r'我的?\s*([^\s，,。.；;是为叫]+)', text)
        if match:
            return match.group(1).strip()
        for kw in mem_type.keywords:
            if kw in text:
                return kw
        return mem_type.display_name

    def format_answer(self, mem_type: MemoryType, value: str, key: str = "") -> str:
        if not key:
            key = mem_type.display_name
        try:
            return mem_type.template.format(value=value, key=key)
        except KeyError:
            return f"{key}是{value}。"


memory_rules = MemoryRuleEngine()