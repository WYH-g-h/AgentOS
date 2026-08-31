# tools/loader.py
"""
工具加载器：从 tools/ 目录动态加载工具
与技能/工作流保持相同的加载模式
支持动态发现和热加载
"""

import importlib.util
from pathlib import Path
from typing import List, Dict, Any

from core.logger import agent_logger
from tools.registry import tool_registry
from core.router import router


# 内置工具文件名（这些是核心工具，不会被热加载覆盖）
BUILTIN_TOOLS = {
    "__init__.py", "base.py", "registry.py", "loader.py",
    "file.py", "command.py",
}


def load_custom_tools(tools_dir: str = "./tools") -> int:
    """
    从 tools/ 目录加载所有工具文件
    跳过内置工具文件，支持动态发现

    Returns:
        int: 加载的工具数量
    """
    tools_path = Path(tools_dir)
    if not tools_path.exists():
        agent_logger.warning(f"工具目录不存在: {tools_dir}")
        return 0

    loaded = 0
    loaded_names = []

    for tool_file in tools_path.glob("*.py"):
        if tool_file.name in BUILTIN_TOOLS or tool_file.name.startswith("__"):
            continue

        try:
            spec = importlib.util.spec_from_file_location(
                f"tools.{tool_file.stem}",
                tool_file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "register"):
                module.register(tool_registry)
                agent_logger.info(f"✅ 加载工具: {tool_file.stem}")
                loaded += 1
                loaded_names.append(tool_file.stem)
            else:
                agent_logger.warning(f"⚠️ 工具 {tool_file.stem} 缺少 register() 函数")

        except Exception as e:
            agent_logger.error(f"❌ 加载工具失败 {tool_file.name}: {e}")

    # 刷新路由映射
    try:
        router.refresh_route_map()
        agent_logger.info(f"✅ 路由映射已刷新（{len(router._route_map)} 条）")
    except Exception as e:
        agent_logger.warning(f"刷新路由映射失败: {e}")

    if loaded > 0:
        agent_logger.info(f"✅ 加载了 {loaded} 个自定义工具: {', '.join(loaded_names)}")
    else:
        agent_logger.info("📭 没有发现新的自定义工具")

    return loaded


def get_custom_tools_info(tools_dir: str = "./tools") -> List[Dict[str, Any]]:
    """获取所有自定义工具的信息（用于前端展示）"""
    tools_path = Path(tools_dir)
    if not tools_path.exists():
        return []

    tools_info = []
    for tool_file in tools_path.glob("*.py"):
        if tool_file.name in BUILTIN_TOOLS or tool_file.name.startswith("__"):
            continue
        tools_info.append({
            "name": tool_file.stem,
            "file": tool_file.name,
            "path": str(tool_file),
        })
    return tools_info
