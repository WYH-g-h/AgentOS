# tools/file.py
"""
文件工具：读、写、删、列、验
包含 robust_modify 健壮修改功能
增强: 原子操作 + 自动备份 + 回滚 + 目录创建
"""

import os
import json
import ast
import tempfile
import shutil
import time
import re
import glob
from pathlib import Path
from datetime import datetime

from .registry import tool_registry
from core.config import config
from core.logger import agent_logger
from core.checker import ExecutionChecker

OUTPUT_DIR = config.get("paths.output", "./output")


def _safe_path(filepath: str) -> str:
    """增强路径安全检查"""
    if not filepath:
        raise ValueError("文件路径为空")

    if "/" not in filepath and "\\" not in filepath:
        base_dir = os.path.abspath(OUTPUT_DIR)
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, filepath)

    filepath = filepath.replace("\\", "/").lstrip("./").lstrip("/")

    if ".." in filepath:
        raise ValueError(f"不允许的路径遍历: {filepath}")

    base_dir = os.path.abspath(OUTPUT_DIR)
    os.makedirs(base_dir, exist_ok=True)

    full_path = os.path.join(base_dir, filepath)
    abs_full = os.path.abspath(full_path)

    if not abs_full.startswith(base_dir):
        raise ValueError(f"路径超出允许范围: {filepath}")

    return abs_full


def atomic_write(filepath: str, content: str, create_backup: bool = True) -> str:
    """
    原子写入：使用临时文件 + os.replace
    增强: 自动创建备份
    """
    try:
        full_path = _safe_path(filepath)
        os.makedirs(os.path.dirname(full_path) or '.', exist_ok=True)

        # 创建备份
        backup_path = None
        if create_backup and os.path.exists(full_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{full_path}.bak_{timestamp}"
            try:
                shutil.copy2(full_path, backup_path)
                agent_logger.debug(f"📂 备份: {backup_path}")
            except Exception as e:
                agent_logger.warning(f"创建备份失败: {e}")

        # 原子写入
        fd, temp_path = tempfile.mkstemp(
            dir=os.path.dirname(full_path),
            prefix='.tmp_',
            suffix='.tmp'
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
            os.replace(temp_path, full_path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        # 清理旧备份（保留最近5个）
        try:
            backup_dir = os.path.dirname(full_path)
            pattern = f"{os.path.basename(full_path)}.bak_*"
            backups = sorted(glob.glob(os.path.join(backup_dir, pattern)))
            for old_backup in backups[:-5]:
                os.remove(old_backup)
        except Exception:
            pass

        return f"✅ 已写入: {filepath}" + (f" (备份: {os.path.basename(backup_path)})" if backup_path else "")

    except ValueError as e:
        return f"❌ 安全限制: {e}"
    except Exception as e:
        return f"❌ 写入失败: {e}"


def robust_modify(filepath: str, user_input: str, content_generator=None) -> str:
    """
    健壮修改：备份 + 回滚 + 多重重试 + 自动修复
    增强: 更完善的备份管理和回滚机制
    """
    agent_logger.info(f"开始健壮修改: {filepath}")

    try:
        full_path = _safe_path(filepath)
    except ValueError as e:
        return f"❌ 安全限制: {e}"

    if not os.path.exists(full_path):
        return f"❌ 文件 {filepath} 不存在"

    # 读取当前内容
    current_content = None
    for attempt in range(3):
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
            break
        except Exception as e:
            if attempt == 2:
                return f"❌ 读取文件失败（已重试3次）: {e}"
            time.sleep(0.5)

    if current_content is None:
        return "❌ 无法读取文件内容"

    # 创建多个备份
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_paths = []

    # 备份1: 时间戳备份
    backup1 = f"{full_path}.bak_{timestamp}"
    try:
        shutil.copy2(full_path, backup1)
        backup_paths.append(backup1)
    except Exception as e:
        return f"❌ 创建备份失败: {e}"

    # 备份2: 最后已知良好版本
    last_good = f"{full_path}.last_good"
    if os.path.exists(last_good):
        try:
            shutil.copy2(full_path, last_good + ".current")
        except Exception:
            pass

    def rollback_all():
        """回滚所有修改"""
        for bp in backup_paths:
            try:
                if os.path.exists(bp):
                    shutil.copy2(bp, full_path)
                    agent_logger.info(f"🔄 回滚: {bp} → {full_path}")
            except Exception as e:
                agent_logger.warning(f"回滚失败 {bp}: {e}")
        for bp in backup_paths:
            try:
                if os.path.exists(bp):
                    os.remove(bp)
            except Exception:
                pass

    def save_last_good():
        """保存为最后良好版本"""
        try:
            shutil.copy2(full_path, last_good)
            agent_logger.debug(f"✅ 保存最后良好版本: {last_good}")
        except Exception as e:
            agent_logger.warning(f"保存最后良好版本失败: {e}")

    # 生成修改方案
    new_content = None

    if content_generator:
        try:
            new_content = content_generator(filepath, current_content, user_input)
        except Exception as e:
            rollback_all()
            return f"❌ 内容生成失败: {e}"
    else:
        from models.manager import model_manager
        from core.health import health_check
        from core.parser import parse_files

        model = model_manager.get_doer()
        if not model:
            rollback_all()
            return "❌ 模型未配置"

        max_attempts = 3
        for attempt in range(max_attempts):
            prompt = f"""文件 {filepath} 当前内容：
{current_content[:3000]}

用户要求：{user_input}

【第{attempt + 1}次尝试】
请输出修改后的完整文件（必须包含完整内容）：
FILE: {filepath}
CONTENT:
[完整的修改后代码]
ENDCONTENT"""

            result, error = health_check.safe_call(model.invoke, prompt, max_retries=2)
            if error:
                continue

            plan = result.content if result else ""
            files = parse_files(plan)

            if filepath in files:
                new_content = files[filepath]
                break
            elif files:
                new_content = list(files.values())[0]
                break

    if not new_content or len(new_content.strip()) < 10:
        rollback_all()
        return "❌ 生成内容失败或内容太短，已回滚"

    # 写入
    temp_path = None
    for attempt in range(3):
        try:
            fd, temp_path = tempfile.mkstemp(
                dir=os.path.dirname(full_path) or '.',
                prefix='.tmp_',
                suffix='.tmp'
            )
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(new_content)
            os.replace(temp_path, full_path)
            temp_path = None
            break
        except Exception as e:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            if attempt == 2:
                rollback_all()
                return f"❌ 写入失败（已重试3次）: {e}，已回滚"
            time.sleep(0.5)

    # 验证
    ok, msg, detail = ExecutionChecker.check_file(filepath, new_content)

    if ok:
        save_last_good()
        for bp in backup_paths:
            try:
                if os.path.exists(bp):
                    os.remove(bp)
            except Exception:
                pass
        try:
            from core.rag import rag
            rag.add("default", {filepath: new_content})
        except Exception:
            pass
        return f"✅ 已修改 {filepath}\n🔍 {msg}"

    # 验证失败，尝试自动修复
    agent_logger.warning(f"验证失败: {msg} {detail}")
    agent_logger.info("尝试自动修复...")

    from models.manager import model_manager
    from core.health import health_check
    from core.parser import parse_files

    model = model_manager.get_doer()
    if model:
        fix_prompt = f"""文件 {filepath} 存在以下问题：
{msg}
{detail}

当前内容：
{new_content[:3000]}

请修复这些问题，输出完整修复后的内容：
FILE: {filepath}
CONTENT:
[修复后的完整代码]
ENDCONTENT"""

        result, error = health_check.safe_call(model.invoke, fix_prompt, max_retries=2)

        if not error and result:
            fix_plan = result.content
            fix_files = parse_files(fix_plan)

            if filepath in fix_files and fix_files[filepath].strip():
                fixed_content = fix_files[filepath]
                ok2, msg2, detail2 = ExecutionChecker.check_file(filepath, fixed_content)

                if ok2:
                    try:
                        fd, temp_path = tempfile.mkstemp(
                            dir=os.path.dirname(full_path) or '.',
                            prefix='.tmp_',
                            suffix='.tmp'
                        )
                        with os.fdopen(fd, 'w', encoding='utf-8') as f:
                            f.write(fixed_content)
                        os.replace(temp_path, full_path)
                        save_last_good()
                        for bp in backup_paths:
                            try:
                                if os.path.exists(bp):
                                    os.remove(bp)
                            except Exception:
                                pass
                        return f"✅ 已修改 {filepath}\n🔧 自动修复成功\n🔍 {msg2}"
                    except Exception as e:
                        agent_logger.warning(f"自动修复写入失败: {e}")

    rollback_all()
    return f"❌ 修改验证失败:\n- {msg}\n- {detail}\n已回滚到原始版本。"


def is_binary_file(filepath: str) -> bool:
    """检查文件是否为二进制文件"""
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except Exception:
        return True


# ============================================================
# 目录和文件创建工具
# ============================================================

def create_directory(dirpath: str) -> str:
    """
    创建目录（支持递归创建）
    """
    if not dirpath:
        return "❌ 目录路径为空"
    try:
        full_path = _safe_path(dirpath)
        os.makedirs(full_path, exist_ok=True)
        return f"✅ 已创建目录: {dirpath}"
    except ValueError as e:
        return f"❌ 安全限制: {e}"
    except Exception as e:
        return f"❌ 创建目录失败: {e}"


def touch_file(filepath: str) -> str:
    """
    创建空文件（如果文件已存在则更新修改时间）
    """
    if not filepath:
        return "❌ 文件路径为空"
    try:
        full_path = _safe_path(filepath)
        # 确保父目录存在
        os.makedirs(os.path.dirname(full_path) or '.', exist_ok=True)
        # 创建或更新文件
        with open(full_path, 'a', encoding='utf-8'):
            os.utime(full_path, None)
        return f"✅ 已创建: {filepath}"
    except ValueError as e:
        return f"❌ 安全限制: {e}"
    except Exception as e:
        return f"❌ 创建文件失败: {e}"


# ============================================================
# 注册工具
# ============================================================

def register_file_tools():
    """注册所有文件工具"""
    tools_config = config.get("tools", {})

    def read_file(filepath: str) -> str:
        if not filepath:
            return "❌ 文件路径为空"
        try:
            full_path = _safe_path(filepath)
            if not os.path.exists(full_path):
                return f"❌ 文件不存在: {filepath}"
            if is_binary_file(full_path):
                return f"⚠️ 文件 {filepath} 是二进制文件"
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return content if content else "📄 文件为空"
        except ValueError as e:
            return f"❌ 安全限制: {e}"
        except UnicodeDecodeError:
            return f"⚠️ 文件 {filepath} 不是文本文件"
        except Exception as e:
            return f"❌ 读取失败: {e}"

    def write_file(filepath: str, content: str) -> str:
        if not filepath:
            return "❌ 文件路径为空"
        if not content:
            return "❌ 内容为空"
        return atomic_write(filepath, content)

    def delete_file(filepath: str) -> str:
        if not filepath:
            return "❌ 文件路径为空"
        try:
            full_path = _safe_path(filepath)
            if not os.path.exists(full_path):
                return f"❌ 文件不存在: {filepath}"
            os.remove(full_path)
            return f"✅ 已删除: {filepath}"
        except ValueError as e:
            return f"❌ 安全限制: {e}"
        except Exception as e:
            return f"❌ 删除失败: {e}"

    def list_files(directory: str = ".") -> str:
        try:
            full_path = _safe_path(directory)
            if not os.path.exists(full_path):
                return f"❌ 目录不存在: {directory}"
            items = os.listdir(full_path)
            if not items:
                return "📭 目录为空"
            lines = [f"📁 {directory}:"]
            for item in sorted(items):
                path = os.path.join(full_path, item)
                if os.path.isdir(path):
                    lines.append(f"  📁 {item}/")
                else:
                    size = os.path.getsize(path)
                    lines.append(f"  📄 {item} ({size} bytes)")
            return "\n".join(lines)
        except ValueError as e:
            return f"❌ 安全限制: {e}"
        except Exception as e:
            return f"❌ 列出失败: {e}"

    def verify_file(filepath: str) -> str:
        if not filepath:
            return "❌ 文件路径为空"
        ok, msg, detail = ExecutionChecker.check_file(filepath)
        return f"{msg}\n{detail}" if detail else msg

    def modify_file(filepath: str, user_input: str) -> str:
        return robust_modify(filepath, user_input)

    # 工具定义
    tool_definitions = [
        ("read_file", read_file, "读取文件内容"),
        ("write_file", write_file, "写入文件内容（原子操作）"),
        ("delete_file", delete_file, "删除文件"),
        ("list_files", list_files, "列出目录文件"),
        ("verify_file", verify_file, "验证文件（Python/JSON/HTML/JS/CSS）"),
        ("modify_file", modify_file, "健壮修改文件（备份+验证+自动修复）"),
        ("mkdir", create_directory, "创建目录（支持递归创建）"),
        ("touch", touch_file, "创建空文件（已存在则更新时间戳）"),
    ]

    registered = 0
    for name, func, desc in tool_definitions:
        enabled = tools_config.get(name, {}).get("enabled", True)
        if enabled:
            tool_registry.register_tool(name, func, desc)
            registered += 1

    print(f"  ✅ 文件工具: {registered}/{len(tool_definitions)}")


def register_memory_tools():
    """
    注册记忆工具
    """
    from core.memory_layer import memory_layer
    from core.cache import memory_cache
    import re

    def remember_info(content: str) -> str:
        content = content.replace("记住", "").replace("记忆", "").strip()
        if not content:
            return "❌ 请提供要记住的内容"
        return memory_layer.add_memory(content, "user_info", "general")

    def recall_memory(keyword: str) -> str:
        cache_key = f"recall:{keyword}"
        cached_result = memory_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        raw_keyword = keyword.strip()
        if not raw_keyword:
            return "📭 请提供要回忆的关键词"

        clean_keyword = raw_keyword
        for prefix in ["回忆", "还记得", "记不记得", "想起", "想起来"]:
            if clean_keyword.startswith(prefix):
                clean_keyword = clean_keyword[len(prefix):].strip()

        if not clean_keyword or len(clean_keyword) < 2:
            match = re.search(r'我的?(\w+)', raw_keyword)
            if match:
                clean_keyword = "我的" + match.group(1)
            else:
                clean_keyword = raw_keyword

        result = memory_layer.search_memory_text(clean_keyword, types=["user_info"], k=3)
        if not result:
            result = memory_layer.search_memory_text(raw_keyword, types=["user_info"], k=3)

        if not result:
            return "📭 没有找到相关记忆"

        final_result = f"📚 {result}"
        memory_cache.set(cache_key, final_result)
        return final_result

    tool_registry.register_tool("remember", remember_info, "记住重要信息")
    tool_registry.register_tool("recall", recall_memory, "回忆记住的信息")
    print("  ✅ 记忆工具: 2 (remember/recall)")


def register_rag_tools():
    """注册 RAG 工具"""
    from core.rag import rag

    def rag_add(project: str = "default", filepath: str = None) -> str:
        if isinstance(project, str) and not filepath:
            parts = project.split()
            if len(parts) >= 2:
                if parts[0] == "rag_add":
                    parts = parts[1:]
                if len(parts) >= 2:
                    project = parts[0]
                    filepath = " ".join(parts[1:])
                else:
                    filepath = parts[0]
                    project = "default"
            else:
                filepath = project
                project = "default"

        if not filepath:
            return "❌ 请指定要添加的文件路径"

        content = tool_registry.execute("read_file", filepath=filepath)
        if "❌" in content:
            return content

        rag.add(project, {filepath: content})
        return f"✅ 已添加 {filepath} 到 RAG 知识库 (项目: {project})"

    def rag_search(query: str, project: str = "default") -> str:
        if isinstance(query, str):
            parts = query.split()
            if len(parts) >= 3 and parts[0] in ["rag_search", "rag search"]:
                project = parts[1]
                query = " ".join(parts[2:])
            elif len(parts) >= 2:
                query = " ".join(parts[1:])

        if not query or len(query.strip()) < 2:
            return "❌ 请提供搜索内容"

        result = rag.search(project, query, k=3)
        return result if result else f"📭 在项目 '{project}' 中没有找到相关信息"

    def rag_ask(query: str, project: str = "default") -> str:
        if isinstance(query, str):
            parts = query.split()
            if len(parts) >= 3 and parts[0] in ["rag_ask", "rag ask"]:
                project = parts[1]
                query = " ".join(parts[2:])
            elif len(parts) >= 2:
                query = " ".join(parts[1:])

        if not query or len(query.strip()) < 2:
            return "❌ 请提供问题"

        return rag.ask(project, query)

    def rag_list(_: str = "") -> str:
        projects = rag.list_projects()
        if not projects:
            return "📭 没有 RAG 项目"
        result = "📚 RAG 项目列表:\n"
        for p in projects:
            result += f"  📁 {p}\n"
        return result

    def rag_stats(_: str = "") -> str:
        return rag.get_stats()

    tool_registry.register_tool("rag_add", rag_add, "添加文件到 RAG 知识库")
    tool_registry.register_tool("rag_search", rag_search, "在 RAG 知识库中搜索")
    tool_registry.register_tool("rag_ask", rag_ask, "基于 RAG 知识库回答问题")
    tool_registry.register_tool("rag_list", rag_list, "列出所有 RAG 项目")
    tool_registry.register_tool("rag_stats", rag_stats, "显示 RAG 统计信息")
    print("  ✅ RAG工具: 5 (add/search/ask/list/stats)")


# 自动注册
from .command import register_command_tools

register_file_tools()
register_memory_tools()
register_rag_tools()
register_command_tools()