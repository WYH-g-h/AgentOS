# core/executor.py
"""
执行引擎：协调模型、工具、技能、工作流的执行
增强规则学习 + 统一工具调用
"""

import time
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .context import ExecutionContext
from .logger import agent_logger
from .parser import extract_filename
from .workflow_engine import WorkflowEngine
from .memory_layer import memory_layer
from .health import health_check


@dataclass
class ExecutorConfig:
    """执行器配置"""
    max_retries: int = 3
    timeout: int = 120
    enable_health_check: bool = True
    stop_on_error: bool = True


class Executor:
    """执行引擎"""

    def __init__(self, config: Optional[ExecutorConfig] = None):
        self.config = config or ExecutorConfig()
        self.workflow_engine = WorkflowEngine()
        self._route_keywords_cache = None

    def _get_route_keywords(self) -> List[str]:
        """
        ✅ 从路由器动态获取所有路由关键词
        支持热加载：每次调用都重新获取
        """
        from core.router import router
        router._ensure_route_map()
        keywords = list(router._route_map.keys())
        keywords.sort(key=len, reverse=True)
        return keywords

    def _strip_route(self, text: str) -> str:
        """
        ✅ 去掉显式路由符号和关键词（兜底）
        正常情况下路由已经剥离了参数，这个只作为兜底
        """
        if not text:
            return text

        # 匹配并移除 [关键词] 或 【关键词】 或 (关键词)
        pairs = [('[', ']'), ('【', '】'), ('(', ')'), ('（', '）')]
        for start_sym, end_sym in pairs:
            if text.startswith(start_sym):
                end_pos = text.find(end_sym)
                if end_pos != -1:
                    text = text[end_pos + 1:].strip()
                    break

        # 去掉路由关键词（如果还残留）
        keywords = self._get_route_keywords()
        if keywords:
            pattern = r'^(' + '|'.join(re.escape(kw) for kw in keywords) + r')\s*'
            text = re.sub(pattern, '', text)

        return text.strip()

    def execute(self, context: ExecutionContext) -> str:
        """执行上下文"""
        context.start_time = time.time()
        agent_logger.info(f"开始执行: {context.user_input[:50]}...")

        try:
            route_type = context.route_result.get("type", "unknown")

            if route_type == "tool":
                result = self._execute_tool(context)
            elif route_type == "skill":
                result = self._execute_skill(context)
            elif route_type == "workflow":
                result = self._execute_workflow(context)
            elif route_type == "chat":
                result = self._execute_chat(context)
            else:
                result = self._execute_chat(context)

            context.end_time = time.time()
            duration = context.end_time - context.start_time
            agent_logger.info(f"执行完成，耗时: {duration:.2f}s")

            return result

        except Exception as e:
            context.add_error(str(e))
            agent_logger.error(f"执行失败: {e}")
            memory_layer.learn_rule(f"执行异常: {e}")
            return f"❌ 执行失败: {e}"

    def _prepare_tool_params(self, tool_name: str, context: ExecutionContext) -> Dict[str, Any]:
        """
        ✅ 统一工具参数准备 - 完整覆盖所有工具
        优先使用路由剥离后的 args
        """
        # ✅ 优先使用路由剥离后的 args
        route_args = context.route_result.get("args", "")
        # 如果 args 为空，使用原始输入（兼容关键词匹配和聊天模式）
        if route_args:
            user_input = route_args
        else:
            user_input = context.user_input

        state = context.state

        # ============================================================
        # 完整的工具参数映射
        # ============================================================
        tool_params_map = {
            # === 文件工具 ===
            "read_file": lambda: {"filepath": extract_filename(user_input) or user_input},
            "write_file": lambda: {
                "filepath": extract_filename(user_input) or state.get("filepath", ""),
                "content": state.get("content", user_input)
            },
            "delete_file": lambda: {"filepath": extract_filename(user_input) or user_input},
            "list_files": lambda: {"directory": extract_filename(user_input) or "."},
            "verify_file": lambda: {"filepath": extract_filename(user_input) or user_input},

            # === 文件修改工具 ===
            "modify_file": lambda: {
                "filepath": extract_filename(user_input) or state.get("filepath", ""),
                "user_input": user_input
            },
            "mkdir": lambda: {"dirpath": extract_filename(user_input) or user_input},
            "touch": lambda: {"filepath": extract_filename(user_input) or user_input},

            # === 命令工具 ===
            "run_command": lambda: self._parse_command_params(user_input),
            "get_time": lambda: {"format_str": self._extract_format(user_input)},
            "get_date": lambda: {"_": ""},
            "get_timestamp": lambda: {"_": ""},

            # === 记忆工具 ===
            "remember": lambda: {"content": user_input.replace("记住", "").replace("记忆", "").strip()},
            "recall": lambda: {"keyword": self._extract_keyword(user_input)},

            # === RAG 工具 ===
            "rag_add": lambda: self._parse_rag_params(user_input, "add"),
            "rag_search": lambda: self._parse_rag_params(user_input, "search"),
            "rag_ask": lambda: self._parse_rag_params(user_input, "ask"),
            "rag_list": lambda: {"_": ""},
            "rag_stats": lambda: {"_": ""},
        }

        if tool_name in tool_params_map:
            return tool_params_map[tool_name]()

        # 默认：传递整个用户输入
        return {"query": user_input}

    def _extract_keyword(self, text: str) -> str:
        """提取关键词（用于 recall）"""
        for prefix in ["回忆", "还记得", "记不记得", "想起", "想起来"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        return text.strip() or text

    def _extract_format(self, text: str) -> str:
        """提取时间格式"""
        format_match = re.search(r'格式[：:]\s*([^\s]+)', text)
        if format_match:
            return format_match.group(1)
        return "%Y-%m-%d %H:%M:%S"

    def _parse_command_params(self, user_input: str) -> Dict[str, Any]:
        """解析命令参数"""
        timeout = 60
        timeout_match = re.search(r'超时[：:]\s*(\d+)', user_input)
        if timeout_match:
            timeout = int(timeout_match.group(1))

        cwd = None
        cwd_match = re.search(r'目录[：:]\s*([^\s]+)', user_input)
        if cwd_match:
            cwd = cwd_match.group(1)

        # 去掉 "超时:xxx" 和 "目录:xxx" 参数
        command = user_input
        command = re.sub(r'超时[：:]\s*\d+', '', command)
        command = re.sub(r'目录[：:]\s*[^\s]+', '', command)
        command = command.strip()

        return {"command": command or user_input, "timeout": timeout, "cwd": cwd}

    def _parse_rag_params(self, user_input: str, operation: str) -> Dict[str, str]:
        """解析 RAG 参数"""
        parts = user_input.split()
        project = "default"
        query = ""

        if len(parts) >= 2:
            if parts[0] in ["rag_add", "rag_search", "rag_ask", "rag_list", "rag_stats"]:
                parts = parts[1:]

            if len(parts) >= 2:
                project = parts[0]
                query = " ".join(parts[1:])
            elif len(parts) == 1:
                query = parts[0]
            else:
                query = user_input
        else:
            query = user_input

        if operation == "add":
            return {"project": project, "filepath": query}
        elif operation in ["search", "ask"]:
            return {"project": project, "query": query}
        return {"_": ""}

    def _execute_tool(self, context: ExecutionContext) -> str:
        """执行工具（统一调用）"""
        from tools.registry import tool_registry

        tool_name = context.route_result.get("target", "")
        tool_spec = tool_registry.get(tool_name)

        if not tool_spec:
            return f"❌ 工具 {tool_name} 不存在"

        agent_logger.info(f"执行工具: {tool_name}")
        agent_logger.flush()

        try:
            params = self._prepare_tool_params(tool_name, context)
            result = tool_spec.func(**params)

            if "✅" in result:
                memory_layer.learn_rule(f"工具 {tool_name} 成功: {context.user_input[:50]}")
            elif "❌" in result:
                memory_layer.learn_rule(f"工具 {tool_name} 失败: {result[:80]}")

            context.set_result(tool_name, result)
            return result
        except Exception as e:
            error_msg = f"工具执行失败: {e}"
            context.add_error(error_msg)
            agent_logger.error(error_msg)
            memory_layer.learn_rule(f"工具 {tool_name} 异常: {e}")
            return f"❌ {error_msg}"

    def _execute_skill(self, context: ExecutionContext) -> str:
        """执行技能（增强规则学习）"""
        from skills.registry import skill_registry

        skill_name = context.route_result.get("target", "")
        skill_spec = skill_registry.get(skill_name)

        if not skill_spec:
            return f"❌ 技能 {skill_name} 不存在"

        if not skill_spec.enabled:
            return f"❌ 技能 {skill_name} 已禁用"

        agent_logger.info(f"执行技能: {skill_name}")
        context.current_skill = skill_name

        handler = skill_registry.get_handler(skill_name)
        if not handler:
            return f"❌ 技能 {skill_name} 未实现"

        try:
            result = handler(context)
            context.set_result(skill_name, result)

            if "✅" in result:
                memory_layer.learn_rule(f"技能 {skill_name} 成功: {context.user_input[:50]}")
                if skill_spec and skill_spec.model:
                    memory_layer.learn_rule(f"技能 {skill_name} 使用模型: {skill_spec.model}")
            elif "❌" in result:
                memory_layer.learn_rule(f"技能 {skill_name} 失败: {result[:80]}")

            return result
        except Exception as e:
            error_msg = f"技能执行失败: {e}"
            context.add_error(error_msg)
            agent_logger.error(error_msg)
            memory_layer.learn_rule(f"技能 {skill_name} 异常: {e}")
            return f"❌ {error_msg}"

    def _execute_workflow(self, context: ExecutionContext) -> str:
        """执行工作流（增强规则学习）"""
        from workflows.registry import workflow_registry

        workflow_name = context.route_result.get("target", "")
        workflow_spec = workflow_registry.get(workflow_name)

        if not workflow_spec:
            return f"❌ 工作流 {workflow_name} 不存在"

        if not workflow_spec.enabled:
            return f"❌ 工作流 {workflow_name} 已禁用"

        agent_logger.info(f"执行工作流: {workflow_name}")
        context.current_workflow = workflow_name

        try:
            result = self.workflow_engine.execute(workflow_spec, context)

            if "✅" in result:
                memory_layer.learn_rule(f"工作流 {workflow_name} 成功: {context.user_input[:50]}")
            elif "❌" in result:
                memory_layer.learn_rule(f"工作流 {workflow_name} 失败: {result[:80]}")

            return result
        except Exception as e:
            error_msg = f"工作流执行失败: {e}"
            context.add_error(error_msg)
            agent_logger.error(error_msg)
            memory_layer.learn_rule(f"工作流 {workflow_name} 异常: {e}")
            return f"❌ {error_msg}"

    def _execute_chat(self, context: ExecutionContext) -> str:
        """执行聊天"""
        from models.manager import model_manager
        from core.session import session_manager

        doer = model_manager.get_doer()
        if not doer:
            return "❌ 执行模型未配置"

        try:
            session = session_manager.get_or_create()
            messages = session.get_messages()

            if messages:
                context_str = session.get_context()
                if context_str:
                    enhanced_input = f"{context.user_input}\n\n[对话历史]\n{context_str}"
                else:
                    enhanced_input = context.user_input
            else:
                enhanced_input = context.user_input

            resp, error = health_check.safe_call(
                doer.invoke, enhanced_input, max_retries=self.config.max_retries
            )

            if error:
                return error

            result = resp.content if resp else "❌ 推理返回空结果"

            session.add_message("user", context.user_input)
            session.add_message("assistant", result)

            return result
        except Exception as e:
            return f"❌ 聊天失败: {e}"