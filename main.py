# main.py
"""
AgentOS v17 主入口
两层路由：显式路由 → 自然语言聊天
"""

import sys
import os
import re
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.config import config
from core.health import health_check
from core.logger import agent_logger
from core.executor import Executor, ExecutorConfig
from core.context import ExecutionContext
from core.session import session_manager, SessionManager
from core.memory_layer import memory_layer
from core.rag import rag
from core.unified_memory import unified
from core.checker import ExecutionChecker, checker
from core.router import router, RouteResult
from core.ui import ui
from core.factory import model_factory
from core.paths import get_skills_dir, get_workflows_dir, ensure_directories, PROJECT_ROOT

from models.registry import model_registry
from models.manager import model_manager

from tools.registry import tool_registry
from tools.file import register_file_tools
from tools.command import register_command_tools

from skills.loader import load_skills
from workflows.loader import load_workflows
from skills.registry import skill_registry
from workflows.registry import workflow_registry


def print_banner():
    """打印启动横幅"""
    print("=" * 60)
    print("🤖 AgentOS v17 - L3 组件化 Agent")
    print("   两层路由: 显式路由 | 自然语言聊天")
    print("=" * 60)
    print(f"📁 工作目录: {os.getcwd()}")
    print(f"📊 模型数: {model_registry.count()}")
    print(f"🔧 工具数: {tool_registry.count()}")
    print(f"📌 技能数: {len(skill_registry._items)}")
    print(f"📋 工作流数: {len(workflow_registry._items)}")
    print(f"💬 会话数: {len(session_manager.list_sessions())}")
    print(f"🧠 知识数: {len(unified.get_all())}")
    print("=" * 60)


def init_agent():
    """初始化Agent"""
    print("🚀 初始化 AgentOS v17...")

    # 确保目录存在
    ensure_directories()

    model_registry.load_defaults()

    errors = config.validate()
    if errors:
        print("❌ 配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False

    print(f"  ✅ 工具: {tool_registry.count()} 个")

    # 使用统一路径
    skills_dir = get_skills_dir()
    load_skills(str(skills_dir))

    workflows_dir = get_workflows_dir()
    load_workflows(str(workflows_dir))

    # 使用 health_check 获取状态
    status = health_check.get_status_summary()
    if status.get("ollama_running", False):
        print(f"  ✅ Ollama: 健康 ({status.get('model_count', 0)} 个模型)")
    else:
        print("  ⚠️ Ollama: 不可用 (请先启动 ollama serve)")

    providers = model_factory.list_providers()
    print(f"  🔌 模型提供者: {', '.join(providers) if providers else '仅 Ollama'}")

    print("✅ AgentOS v17 初始化完成")
    return True


def load_triggers_from_config():
    """从技能和工作流配置动态加载触发器（仅用于显示）"""
    triggers = {
        "skill": {},
        "workflow": {},
        "tool": {}
    }

    for name, spec in skill_registry._items.items():
        if spec.enabled:
            for trigger in spec.triggers:
                triggers["skill"][trigger] = name

    for name, spec in workflow_registry._items.items():
        if spec.enabled:
            for trigger in spec.triggers:
                triggers["workflow"][trigger] = name

    return triggers


def route_with_router(user_input: str, session=None) -> dict:
    """使用路由器进行路由"""
    result: RouteResult = router.route(user_input, session)
    return {
        "type": result.type,
        "target": result.target,
        "confidence": result.confidence,
        "reason": result.reason,
        "args": result.args,
        "metadata": result.metadata or {}
    }


def route_with_fallback(user_input: str, triggers: dict, session=None) -> dict:
    """路由主入口"""
    return route_with_router(user_input, session)


def process_with_memory(user_input: str, context: ExecutionContext) -> str:
    """处理用户输入，注入知识（仅用于自然语言）"""
    enhanced_input = user_input

    # 自动提取用户画像
    query_patterns = ["什么", "吗", "？", "?", "哪", "多", "几", "怎么", "如何", "谁", "哪里", "什么时候"]
    profile_keywords = ["我", "我的", "我是", "叫", "岁", "生日", "学校", "大学",
                        "工作", "职业", "爱好", "喜欢", "家乡", "专业", "在读",
                        "就读", "毕业", "今年", "出生", "手机", "电话", "邮箱"]

    should_extract = any(kw in user_input for kw in profile_keywords)
    is_query = any(p in user_input for p in query_patterns)

    if should_extract and not is_query:
        result = memory_layer.auto_extract_and_save(user_input)
        if result:
            ui.show_success(result)

    # 统一检索
    if any(kw in user_input for kw in ["我", "我的", "名字", "年龄", "生日"]):
        memory_result = memory_layer.search_memory(user_input[:50], types=["user_info"], k=3)
        if memory_result:
            ui.show_info("找到相关记忆")
            lines = ["【相关记忆】"]
            for item in memory_result:
                content = item.get("content", "")
                category = item.get("category", "")
                display = unified.USER_INFO_CATEGORIES.get(category, category)
                lines.append(f"- [{display}] {content}")
            memory_hint = "\n".join(lines)
            enhanced_input = f"{enhanced_input}\n\n{memory_hint}"
            context.set_state("memory_hint", memory_hint)

    if len(user_input) > 5:
        doc_result = memory_layer.search_memory(user_input, types=["document"], k=2)
        if doc_result:
            ui.show_info("找到相关知识")
            lines = ["【相关知识】"]
            for item in doc_result[:2]:
                content = item.get("content", "")[:150]
                lines.append(f"- {content}...")
            doc_hint = "\n".join(lines)
            enhanced_input = f"{enhanced_input}\n\n{doc_hint}"
            context.set_state("doc_hint", doc_hint)

    rules = memory_layer.get_rules(user_input)
    if rules:
        enhanced_input = f"{enhanced_input}\n\n{rules}"
        context.set_state("rules_applied", True)

    return enhanced_input


def print_health_status():
    """打印健康状态（复用 health_check）"""
    status = health_check.get_status_summary()

    print("🔍 系统健康状态:")
    print("-" * 40)

    if status.get("ollama_running", False):
        print("  ✅ Ollama: 运行中")
        models = status.get("models", [])
        if models:
            print(f"  📦 可用模型 ({len(models)} 个):")
            for m in models:
                name = m.get("name", "")
                size = m.get("size", 0) / (1024 ** 3)
                print(f"      📌 {name} ({size:.1f} GB)")
        else:
            print("  📭 没有已下载的模型")
    else:
        print("  ❌ Ollama: 未运行 (请启动: ollama serve)")

    return status


def interactive_shell():
    """交互式命令行"""
    executor = Executor(ExecutorConfig(max_retries=3))

    current_session = session_manager.get_or_create()
    ui.show_info(f"会话: {current_session.session_id}")
    print("   提示: 输入 /help 查看命令")

    triggers = load_triggers_from_config()

    while True:
        try:
            user_input = input("\n🧑 你: ").strip()

            if not user_input:
                continue

            # ============================================================
            # 命令处理
            # ============================================================
            if user_input.startswith("/"):
                cmd = user_input.lower()

                if cmd in ["/exit", "/quit"]:
                    current_session.save()
                    ui.show_success(f"会话已保存: {current_session.session_id}")
                    stats = unified.get_stats()
                    print(f"📊 知识库统计: {stats['total']} 条知识")
                    break

                elif cmd == "/tools":
                    print(tool_registry.list_descriptions())

                elif cmd == "/skills":
                    print("\n📌 可用技能:")
                    for name, spec in skill_registry._items.items():
                        status = "✅" if spec.enabled else "❌"
                        triggers_list = ", ".join(spec.triggers[:3])
                        print(f"  {status} {name}: {spec.description} (触发: {triggers_list})")

                elif cmd == "/workflows":
                    print("\n📋 可用工作流:")
                    for name, spec in workflow_registry._items.items():
                        status = "✅" if spec.enabled else "❌"
                        triggers_list = ", ".join(spec.triggers[:3])
                        print(f"  {status} {name}: {spec.description} ({len(spec.steps)} 步) (触发: {triggers_list})")

                elif cmd == "/models":
                    print("\n🧠 可用模型:")
                    for spec in model_registry.list_all():
                        caps = ", ".join(c.value for c in spec.capabilities)
                        print(f"  📌 {spec.name}")
                        print(f"     能力: {caps}")
                        print(f"     速度: {spec.speed_score} | 质量: {spec.quality_score}")

                    # 复用 health_check 显示状态
                    print("\n🔌 服务状态:")
                    status = health_check.get_status_summary()
                    if status.get("ollama_running", False):
                        print(f"  ✅ Ollama: 运行中 ({status.get('model_count', 0)} 个模型)")
                    else:
                        print("  ❌ Ollama: 未运行")

                elif cmd == "/sessions":
                    sessions = session_manager.list_sessions()
                    print(f"\n💬 会话列表 ({len(sessions)}):")
                    current_id = current_session.session_id
                    for sid in sessions:
                        marker = "👉 " if sid == current_id else "   "
                        print(f"  {marker}{sid}")

                elif cmd.startswith("/switch "):
                    new_session_id = cmd[8:].strip()
                    current_session = session_manager.get_or_create(new_session_id)
                    ui.show_success(f"切换到会话: {current_session.session_id}")

                elif cmd == "/new":
                    current_session = session_manager.get_or_create()
                    ui.show_success(f"新会话: {current_session.session_id}")


                elif cmd == "/reload":
                    config.reload()
                    # 使用统一路径
                    skills_dir = get_skills_dir()
                    load_skills(str(skills_dir))
                    workflows_dir = get_workflows_dir()
                    load_workflows(str(workflows_dir))
                    # 刷新路由映射
                    router.refresh_route_map()
                    router.clear_cache()
                    # 刷新模型注册表
                    model_registry.load_defaults()
                    # 刷新记忆层
                    # memory_layer 会重新加载
                    print_banner()
                    ui.show_success("配置、技能、工作流和模型已重新加载")

                elif cmd == "/memory":
                    user_items = unified.get_user_info()
                    if not user_items:
                        ui.show_info("用户信息为空")
                    else:
                        print(f"📚 用户信息 ({len(user_items)} 条):")
                        for i, item in enumerate(user_items[-10:], 1):
                            category = item.get("category", "unknown")
                            content = item.get("content", "")
                            display = unified.USER_INFO_CATEGORIES.get(category, category)
                            print(f"  {i}. [{display}] {content}")
                        if len(user_items) > 10:
                            print(f"  ... 还有 {len(user_items) - 10} 条")
                    continue

                elif cmd == "/rag":
                    doc_items = unified.get_by_type("document")
                    stats = unified.get_stats()
                    print(f"📊 知识库统计:")
                    print(f"  总知识: {stats['total']} 条")
                    print(f"  文档: {len(doc_items)} 个片段")
                    print(f"  用户信息: {len(unified.get_user_info())} 条")
                    print(f"  规则: {len(unified.get_by_type('rule'))} 条")
                    continue

                elif cmd == "/rules":
                    print("\n📋 经验规则:")
                    rules = unified.get_by_type("rule")
                    if not rules:
                        ui.show_info("暂无经验规则")
                    else:
                        print(f"  共 {len(rules)} 条规则:")
                        for rule in rules[-10:]:
                            content = rule.get("content", "")
                            rule_time = rule.get("time", "")
                            print(f"  📌 [{rule_time}] {content[:60]}")
                    continue

                elif cmd == "/health":
                    print_health_status()
                    continue

                elif cmd == "/integrate":
                    result = memory_layer.integrate_to_rag(force=False)
                    ui.show_success(result)

                elif cmd == "/verify":
                    ui.show_info("验证项目文件...")
                    output_dir = config.get("paths.output", "./output")
                    files = []
                    for root, dirs, filenames in os.walk(output_dir):
                        for filename in filenames:
                            if filename.endswith(('.py', '.json', '.html', '.js', '.css', '.md', '.yaml', '.yml')):
                                rel_path = os.path.relpath(os.path.join(root, filename), output_dir)
                                files.append(rel_path)

                    if not files:
                        ui.show_info("没有找到可验证的文件")
                        continue

                    print(f"📁 找到 {len(files)} 个文件")
                    results = ExecutionChecker.check_multiple_files(files)
                    passed = 0
                    for fp, (ok, msg, detail) in results.items():
                        if ok:
                            passed += 1
                            print(f"  ✅ {fp}: {msg}")
                        else:
                            print(f"  ❌ {fp}: {msg}")
                            if detail:
                                print(f"      📝 {detail}")
                    ui.show_success(f"通过: {passed}/{len(files)}")
                    continue

                elif cmd == "/stats":
                    print("\n📊 系统统计:")
                    print(f"  📌 知识库: {len(unified.get_all())} 条")
                    print(f"  📌 会话: {len(session_manager.list_sessions())} 个")
                    route_stats = router.get_stats()
                    print(f"  📌 路由缓存: {route_stats.get('cache_size', 0)} 条")
                    print(f"  📌 显式路由: {route_stats.get('explicit_hits', 0)} 次")
                    print(f"  📌 聊天模式: {route_stats.get('chat_hits', 0)} 次")
                    print(f"  📌 路由映射: {route_stats.get('route_map_size', 0)} 条")
                    memory_stats = memory_layer.get_memory_status()
                    print(f"  📌 记忆类型: {memory_stats.get('by_type', {})}")
                    continue

                elif cmd == "/route":
                    print(router.list_commands())
                    continue

                elif cmd == "/route_stats":
                    stats = router.get_stats()
                    print(f"📊 路由统计:")
                    print(f"  显式路由: {stats['explicit_hits']} 次")
                    print(f"  聊天模式: {stats['chat_hits']} 次")
                    print(f"  缓存命中: {stats['cache_hits']} 次")
                    print(f"  解析错误: {stats['parse_errors']} 次")
                    print(f"  缓存大小: {stats['cache_size']} 条")
                    print(f"  路由映射: {stats['route_map_size']} 条")
                    print(f"  总路由数: {stats['total_hits']} 次")
                    continue

                elif cmd == "/route_clear":
                    router.clear_cache()
                    ui.show_success("路由缓存已清空")
                    continue

                elif cmd == "/help":
                    print("""
命令列表:
/exit, /quit     - 退出
/tools           - 列出工具
/skills          - 列出技能
/workflows       - 列出工作流
/models          - 列出模型
/sessions        - 列出会话
/switch [id]     - 切换会话
/new             - 新建会话
/reload          - 重新加载配置
/memory          - 查看用户信息
/rag             - 查看RAG统计
/rules           - 查看经验规则
/health          - 健康检查 + 模型列表
/integrate       - 整合记忆到RAG
/verify          - 验证所有项目文件
/stats           - 系统统计
/route           - 查看显式路由命令列表
/route_stats     - 查看路由统计
/route_clear     - 清空路由缓存
/help            - 显示帮助

💡 显式路由用法（支持在句子任何位置）:
  [创建] index.html   → 创建文件
  【总结】test.txt    → 总结文件
  (生成代码)          → 执行代码生成工作流
  [分析] data.csv     → 分析数据
  帮我【创建】文件     → 在句子中间也支持

💡 自然语言直接聊天:
  你好               → 直接聊天
                    """)
                continue

            # ============================================================
            # 正常用户输入处理
            # ============================================================
            print("🤖 ", end="", flush=True)
            start_time = time.time()

            context = ExecutionContext(user_input=user_input, route_result={})
            context.set_state("session_id", current_session.session_id)

            is_explicit = router.is_explicit_route(user_input)

            if is_explicit:
                route_result = route_with_fallback(user_input, triggers, current_session)
                context.route_result = route_result
                result = executor.execute(context)
            else:
                enhanced_input = process_with_memory(user_input, context)
                route_result = route_with_fallback(enhanced_input, triggers, current_session)
                context.route_result = route_result
                result = executor.execute(context)

            route_type = route_result.get("type", "unknown")
            route_target = route_result.get("target", "")
            route_confidence = route_result.get("confidence", 0)
            route_reason = route_result.get("reason", "")

            print(f"  🧭 → {route_type}: {route_target} (置信度: {route_confidence:.2f})", end="")
            if route_reason:
                print(f" [{route_reason}]", end="")
            print()

            elapsed_seconds = time.time() - start_time
            if elapsed_seconds > 5:
                print(f"  ⏱️ 耗时: {elapsed_seconds:.1f}s")

            print(result)
            sys.stdout.flush()

        except KeyboardInterrupt:
            current_session.save()
            ui.show_success(f"会话已保存: {current_session.session_id}")
            break
        except Exception as e:
            ui.show_error(f"错误: {e}")
            import traceback
            traceback.print_exc()


def main():
    """主入口"""
    if not init_agent():
        print("❌ 初始化失败，请检查配置")
        return

    print_banner()

    print("🧭 路由模式: 显式路由 [命令] → 自然语言聊天")
    print("💡 使用 /route 查看所有显式路由命令")
    print()

    interactive_shell()


if __name__ == "__main__":
    main()