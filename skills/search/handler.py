# skills/search/handler.py
"""
搜索技能：在文件或目录中搜索内容
支持按文件名搜索和按内容搜索
"""

import os
import re
from pathlib import Path
from core.logger import agent_logger
from core.parser import extract_filename
from core.health import health_check
from tools.registry import tool_registry
from models.manager import model_manager
from skills.registry import skill_registry


def _search_by_filename(keyword: str, search_dir: str = ".") -> str:
    """按文件名搜索"""
    # 提取文件名的核心部分
    filename_pattern = keyword
    # 如果是完整文件名，直接匹配
    is_exact = "." in filename_pattern

    list_result = tool_registry.execute("list_files", directory=search_dir)
    if "❌" in list_result:
        return list_result

    # 解析文件列表
    files = []
    for line in list_result.split("\n"):
        if "📄" in line:
            parts = line.split("📄")[1].strip().split(" ")
            if parts:
                files.append(parts[0])

    if not files:
        return f"📭 在 {search_dir} 中没有找到任何文件"

    # 匹配文件
    if is_exact:
        matches = [f for f in files if f == filename_pattern]
    else:
        matches = [f for f in files if filename_pattern in f]

    if not matches:
        return f"📭 在 {search_dir} 中没有找到包含 '{keyword}' 的文件名"

    result = f"🔍 找到 {len(matches)} 个匹配的文件:\n"
    for f in matches:
        result += f"  📄 {f}\n"
    return result


def _search_by_content(keyword: str, search_dir: str = ".") -> str:
    """按文件内容搜索"""
    list_result = tool_registry.execute("list_files", directory=search_dir)
    if "❌" in list_result:
        return list_result

    # 解析文件列表
    files = []
    for line in list_result.split("\n"):
        if "📄" in line:
            parts = line.split("📄")[1].strip().split(" ")
            if parts:
                files.append(parts[0])

    if not files:
        return f"📭 在 {search_dir} 中没有找到任何文件"

    agent_logger.debug(f"搜索 {len(files)} 个文件的内容...")

    results = []
    max_files = 10

    for filepath in files[:max_files]:
        full_path = os.path.join(search_dir, filepath)
        content = tool_registry.execute("read_file", filepath=full_path)

        if "❌" in content:
            continue

        if keyword.lower() in content.lower():
            lines = content.split("\n")
            matches = []
            for i, line in enumerate(lines):
                if keyword.lower() in line.lower():
                    start = max(0, i - 1)
                    end = min(len(lines), i + 2)
                    context_lines = lines[start:end]
                    matches.append({
                        "line": i + 1,
                        "content": line.strip(),
                        "context": "\n".join(context_lines).strip()
                    })

            if matches:
                results.append({
                    "file": filepath,
                    "matches": matches
                })

    if not results:
        return f"📭 在 {search_dir} 中没有找到包含 '{keyword}' 的内容"

    # 使用 LLM 总结搜索结果
    prompt = f"""用户搜索关键词: {keyword}
    搜索结果:
    """
    for r in results[:5]:
        prompt += f"\n文件: {r['file']}\n"
        for match in r['matches'][:3]:
            prompt += f"  行 {match['line']}: {match['content']}\n"

    prompt += f"""
请总结搜索结果，告诉用户：
1. 找到了哪些文件包含该关键词
2. 每个文件中大概是什么内容
3. 总共有多少结果

用简洁、清晰的语言回答。
"""

    result, error = health_check.safe_call(
        model_manager.get_router().invoke, prompt, max_retries=1
    )

    if not error and result:
        return f"🔍 搜索结果:\n{result.content.strip()}"

    # 降级：直接返回文件列表
    file_list = "\n".join([f"  📄 {r['file']} ({len(r['matches'])} 处匹配)" for r in results[:5]])
    return f"🔍 找到 {len(results)} 个文件包含 '{keyword}':\n{file_list}"


def handler(context) -> str:
    """搜索技能实现"""
    agent_logger.info(f"执行搜索技能: {context.user_input[:50]}...")

    skill_spec = skill_registry.get(context.current_skill)
    if skill_spec and skill_spec.model:
        model = model_manager.get_model_by_config(skill_spec.model)
        retries = skill_spec.retries
    else:
        model = model_manager.get_router()
        retries = 2

    if not model:
        return "❌ 模型未配置"

    # 提取搜索关键词
    keyword = context.user_input
    keyword = re.sub(r'^(搜索|查找|找|寻找|搜一下)\s*', '', keyword).strip()

    if not keyword or len(keyword) < 2:
        return "❌ 请提供搜索关键词"

    agent_logger.debug(f"搜索关键词: {keyword}")

    # 提取搜索目录
    dir_match = re.search(r'在\s*([^\s]+)\s*中', keyword)
    if dir_match:
        search_dir = dir_match.group(1)
        keyword = keyword.replace(f"在{search_dir}中", "").strip()
    else:
        search_dir = "."

    #  检测是否是文件名搜索
    is_filename_search = bool(re.search(r'[a-zA-Z0-9_\-\.]+\.\w+', keyword))
    # 或者关键词本身就是文件名格式
    if is_filename_search or ('.' in keyword and len(keyword.split('.')) > 1):
        agent_logger.debug(f"按文件名搜索: {keyword}")
        return _search_by_filename(keyword, search_dir)

    # 按内容搜索
    return _search_by_content(keyword, search_dir)