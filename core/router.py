# core/router.py
"""
三层显式路由器 + 关键词匹配
优先级: 显式路由（【】[] ()）> 关键词匹配 > 聊天
"""

import re
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

from core.logger import agent_logger
from core.cache import Cache


@dataclass
class RouteResult:
    """路由结果"""
    type: str  # tool, skill, workflow, chat
    target: str
    confidence: float
    reason: str
    args: str = ""  # 剥离后的纯参数
    metadata: Dict[str, Any] = None


class Router:
    """三层显式路由器 + 关键词匹配"""

    _instance = None
    _route_map: Dict[str, Tuple[str, str]] = {}
    _map_built = False

    TOOL_ALIASES = {
        "read_file": "读取",
        "write_file": "写入",
        "delete_file": "删除",
        "list_files": "列出",
        "verify_file": "验证",
        "modify_file": "修改",
        "mkdir": "建目录",
        "touch": "建文件",
        "run_command": "执行",
        "remember": "记住",
        "recall": "回忆",
        "rag_add": "加知识",
        "rag_search": "搜知识",
        "rag_ask": "问知识",
        "rag_list": "知识列表",
        "rag_stats": "知识统计",
        "get_time": "时间",
        "get_date": "日期",
        "get_timestamp": "戳",
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._route_cache = Cache(max_size=100, ttl=300, name="route")

        # 路由符号配置
        self.start_symbols = ["[", "【", "(", "（"]
        self.end_symbols = ["]", "】", ")", "）"]
        self.pair_map = {
            "[": "]", "【": "】", "(": ")", "（": "）",
            "]": "[", "】": "【", ")": "(", "）": "（",
        }

        self._stats = {
            "explicit_hits": 0,
            "keyword_hits": 0,
            "chat_hits": 0,
            "cache_hits": 0,
            "parse_errors": 0,
        }

        # 关键词黑名单：这些词不会被用于关键词匹配（避免误触发）
        self.keyword_blacklist = {
            "我", "你", "他", "她", "它", "我们", "你们", "他们",
            "什么", "怎么", "为什么", "哪里", "谁", "哪个", "哪些",
            "是", "的", "了", "吗", "呢", "吧", "啊", "哦",
            "请", "帮", "想", "要", "能", "可以", "会", "有",
            "这个", "那个", "一个", "一些", "所有", "全部",
        }

    # ============================================================
    # 动态构建路由映射
    # ============================================================

    def _ensure_route_map(self):
        """确保路由映射已构建（支持热插拔）"""
        if self._map_built:
            return

        self._route_map = {}

        # 1. 从技能注册表读取
        try:
            from skills.registry import skill_registry
            for name, spec in skill_registry._items.items():
                if spec.enabled:
                    if spec.triggers:
                        primary_trigger = spec.triggers[0]
                        self._route_map[primary_trigger] = ("skill", name)
                    else:
                        self._route_map[name] = ("skill", name)
            agent_logger.debug(f"加载 {len(skill_registry._items)} 个技能到路由映射")
        except Exception as e:
            agent_logger.debug(f"加载技能到路由映射失败: {e}")

        # 2. 从工作流注册表读取
        try:
            from workflows.registry import workflow_registry
            for name, spec in workflow_registry._items.items():
                if spec.enabled:
                    if spec.triggers:
                        primary_trigger = spec.triggers[0]
                        self._route_map[primary_trigger] = ("workflow", name)
                    else:
                        self._route_map[name] = ("workflow", name)
            agent_logger.debug(f"加载 {len(workflow_registry._items)} 个工作流到路由映射")
        except Exception as e:
            agent_logger.debug(f"加载工作流到路由映射失败: {e}")

        # 3. 从工具注册表读取
        try:
            from tools.registry import tool_registry
            for name in tool_registry.list_names():
                alias = self.TOOL_ALIASES.get(name, name)
                self._route_map[alias] = ("tool", name)
            agent_logger.debug(f"加载 {tool_registry.count()} 个工具到路由映射")
        except Exception as e:
            agent_logger.debug(f"加载工具到路由映射失败: {e}")

        self._map_built = True
        agent_logger.debug(f"路由映射构建完成，共 {len(self._route_map)} 条")

    def refresh_route_map(self):
        """刷新路由映射"""
        self._map_built = False
        self._route_cache.clear()
        self._ensure_route_map()
        agent_logger.info("🔄 路由映射已刷新")

    # ============================================================
    # 工具别名动态刷新
    # ============================================================

    def refresh_tool_aliases(self):
        """
        刷新工具别名（用于热加载）
        从工具注册表动态更新 TOOL_ALIASES
        """
        try:
            from tools.registry import tool_registry

            # 获取所有已注册的工具名称
            tool_names = tool_registry.list_names()

            # 更新别名：保留已有的中文别名，新工具自动生成
            for name in tool_names:
                if name not in self.TOOL_ALIASES:
                    # 自动生成中文名（去掉下划线）
                    display_name = name.replace('_', '')
                    # 如果是纯英文，首字母大写
                    if display_name.isalpha() and display_name.isascii():
                        display_name = display_name.capitalize()
                    self.TOOL_ALIASES[name] = display_name

            # 刷新路由映射
            self._map_built = False
            self._route_cache.clear()
            self._ensure_route_map()
            agent_logger.info(f"🔄 工具别名已刷新，共 {len(self.TOOL_ALIASES)} 个工具")
            return True
        except Exception as e:
            agent_logger.error(f"刷新工具别名失败: {e}")
            return False

    def get_tool_alias(self, tool_name: str) -> str:
        """获取工具的中文别名"""
        return self.TOOL_ALIASES.get(tool_name, tool_name)

    # ============================================================
    # 显式路由解析
    # ============================================================

    def _parse_explicit_route(self, text: str) -> Optional[Tuple[str, str, str]]:
        """
        解析显式路由：【关键词】参数
        返回: (关键词, 剥离后的参数, 匹配的符号)
        """
        if not text:
            return None

        state = 0
        keyword = ""
        matched_start = ""
        matched_end = ""
        end_index = -1

        i = 0
        while i < len(text):
            char = text[i]

            if state == 0:
                if char in self.start_symbols:
                    state = 1
                    matched_start = char
                    keyword = ""
                    i += 1
                    continue
                i += 1
                continue

            if state == 1:
                if char in self.end_symbols:
                    expected_end = self.pair_map.get(matched_start, "")
                    if char == expected_end:
                        state = 0
                        matched_end = char
                        end_index = i
                        if keyword:
                            keyword = keyword.strip()
                            args = text[end_index + 1:].strip()
                            return (keyword, args, f"{matched_start}{matched_end}")
                        return None
                    else:
                        state = 0
                        i += 1
                        continue
                else:
                    keyword += char
                    i += 1
                    continue

        return None

    # ============================================================
    # 关键词匹配
    # ============================================================

    def _match_keyword(self, user_input: str) -> Optional[RouteResult]:
        """
        关键词匹配：检测用户输入中是否包含路由关键词
        优先级：先匹配长词（如"数据分析"），再匹配短词（如"分析"）
        """
        self._ensure_route_map()

        # 按关键词长度降序排列（优先匹配长词）
        sorted_keywords = sorted(self._route_map.keys(), key=len, reverse=True)

        # 过滤黑名单
        filtered_keywords = [
            kw for kw in sorted_keywords
            if kw not in self.keyword_blacklist
        ]

        for keyword in filtered_keywords:
            if self._is_whole_word_match(user_input, keyword):
                route_type, target = self._route_map[keyword]
                agent_logger.info(f"🔑 关键词匹配: '{keyword}' → {route_type}:{target}")
                return RouteResult(
                    route_type,
                    target,
                    0.85,
                    f"关键词匹配: {keyword}",
                    args=user_input,
                    metadata={"matched_keyword": keyword, "raw": user_input}
                )

        return None

    def _is_whole_word_match(self, text: str, keyword: str) -> bool:
        """检查关键词是否在文本中作为"独立词"出现"""
        if keyword not in text:
            return False

        start = 0
        while True:
            pos = text.find(keyword, start)
            if pos == -1:
                break

            before_ok = pos == 0 or not text[pos - 1].isalnum()
            after_ok = pos + len(keyword) >= len(text) or not text[pos + len(keyword)].isalnum()

            if before_ok and after_ok:
                return True

            start = pos + 1

        return False

    # ============================================================
    # 主路由方法
    # ============================================================

    def route(self, user_input: str, session=None) -> RouteResult:
        """三层路由: 显式路由 → 关键词匹配 → 聊天"""
        if not user_input or not user_input.strip():
            return RouteResult("chat", "chat", 0.0, "空输入")

        cache_key = f"route:{user_input[:50]}"
        cached = self._route_cache.get(cache_key)
        if cached:
            self._stats["cache_hits"] += 1
            return cached

        self._ensure_route_map()

        # Level 1: 显式路由（最高优先级）
        result = self._match_explicit(user_input)
        if result:
            self._stats["explicit_hits"] += 1
            self._route_cache.set(cache_key, result)
            return result

        # Level 2: 关键词匹配
        result = self._match_keyword(user_input)
        if result:
            self._stats["keyword_hits"] += 1
            self._route_cache.set(cache_key, result)
            return result

        # Level 3: 聊天（兜底）
        self._stats["chat_hits"] += 1
        result = RouteResult("chat", "chat", 0.5, "聊天模式")
        self._route_cache.set(cache_key, result)
        return result

    def _match_explicit(self, user_input: str) -> Optional[RouteResult]:
        """匹配显式路由"""
        parsed = self._parse_explicit_route(user_input)
        if not parsed:
            return None

        keyword, args, matched_symbols = parsed

        if keyword in self._route_map:
            route_type, target = self._route_map[keyword]
            return RouteResult(
                route_type,
                target,
                0.99,
                f"显式路由 {matched_symbols}: {keyword}",
                args=args,
                metadata={"raw": user_input}
            )
        else:
            agent_logger.debug(f"未知路由命令: {keyword}")
            self._stats["parse_errors"] += 1
            return None

    # ============================================================
    # 辅助方法
    # ============================================================

    def is_explicit_route(self, user_input: str) -> bool:
        """判断输入是否包含显式路由符号"""
        user_input = user_input.strip()
        return any(s in user_input for s in self.start_symbols)

    def get_stats(self) -> Dict:
        """获取路由统计"""
        return {
            "explicit_hits": self._stats["explicit_hits"],
            "keyword_hits": self._stats["keyword_hits"],
            "chat_hits": self._stats["chat_hits"],
            "cache_hits": self._stats["cache_hits"],
            "parse_errors": self._stats["parse_errors"],
            "cache_size": len(self._route_cache._cache),
            "total_hits": sum(self._stats.values()),
            "route_map_size": len(self._route_map),
        }

    def clear_cache(self):
        """清空路由缓存"""
        self._route_cache.clear()
        agent_logger.info("路由缓存已清空")

    def list_commands(self) -> str:
        """列出所有显式路由命令"""
        self._ensure_route_map()

        lines = ["📋 显式路由命令列表:"]
        lines.append("")
        lines.append("  ✅ 支持在句子任何位置！")
        lines.append("  格式: [命令] 参数")
        lines.append("  格式: 【命令】参数")
        lines.append("  格式: (命令) 参数")
        lines.append("")
        lines.append("  ✅ 也支持自然语言关键词匹配：")
        lines.append("    输入: 帮我分析一下这个文件")
        lines.append("    → 自动匹配 '分析' 关键词，路由到 analyze 技能")
        lines.append("")
        lines.append("  ✅ 示例:")
        lines.append("    你: [创建] index.html")
        lines.append("    你: 帮我【总结】test.txt")
        lines.append("    你: 分析 data.csv")
        lines.append("")

        by_type = {"skill": [], "workflow": [], "tool": []}
        for cmd, (rtype, target) in self._route_map.items():
            if rtype in by_type:
                by_type[rtype].append((cmd, target))

        type_names = {
            "skill": "🎯 技能",
            "workflow": "📋 工作流",
            "tool": "🔧 工具",
        }

        for rtype, items in by_type.items():
            if items:
                lines.append(f"  {type_names.get(rtype, rtype)}:")
                seen = set()
                for cmd, target in sorted(items):
                    if (cmd, target) not in seen:
                        seen.add((cmd, target))
                        lines.append(f"    {cmd} → {target}")

        return "\n".join(lines)


# 全局路由器实例
router = Router()