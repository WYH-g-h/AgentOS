# tools/command.py
"""
命令执行工具：安全执行系统命令
包含 run_command、get_current_time、get_current_date、get_timestamp
"""

import shlex
import subprocess
import sys
import os
from datetime import datetime
from typing import Optional

from .registry import tool_registry
from core.config import config
from core.logger import agent_logger


def run_command(command: str, timeout: int = 60, cwd: Optional[str] = None) -> str:
    """
    执行系统命令，带安全过滤

    Args:
        command: 要执行的命令
        timeout: 超时时间（秒）
        cwd: 工作目录（默认使用 output 目录）

    Returns:
        str: 执行结果
    """
    if not command or not command.strip():
        return "❌ 命令为空"

    cmd = command.strip()
    agent_logger.info(f"执行命令: {cmd[:100]}")

    # ============================================================
    # 第一层：字符级安全过滤
    # ============================================================
    FORBIDDEN_PATTERNS = [
        '|', '&', ';', '>', '<', '`', '$', '&&', '||',
        '>>', '2>', '2>&1',
    ]
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in cmd:
            return f"❌ 安全限制: 命令包含禁止字符 '{pattern}'"

    # ============================================================
    # 第二层：危险命令过滤
    # ============================================================
    DANGEROUS_COMMANDS = [
        "rm -rf /", "rm -rf /*", "dd if=", "mkfs", "format",
        "shutdown", "reboot", "halt", "poweroff",
        "chmod 777 /", "chown -R", "chown -r",
        "kill -9", "killall", "pkill",
        "sudo", "su ", "passwd", "chpasswd",
        "wget http", "curl http", "nc -", "telnet",
    ]
    cmd_lower = cmd.lower()
    for d in DANGEROUS_COMMANDS:
        if d in cmd_lower:
            return f"❌ 安全限制: 禁止执行 '{d}'"

    # ============================================================
    # 第三层：命令解析
    # ============================================================
    try:
        args = shlex.split(cmd)
    except ValueError as e:
        return f"❌ 命令解析失败: {e}"

    if not args:
        return "❌ 命令解析为空"

    executable = args[0].lower()

    # ============================================================
    # 第四层：Python/pip 命令重定向到当前解释器
    # ============================================================
    if executable in ("python", "python3"):
        args[0] = sys.executable
    elif executable in ("pip", "pip3"):
        args = [sys.executable, "-m", "pip"] + args[1:]

    # ============================================================
    # 第五层：确定工作目录
    # ============================================================
    if cwd is None:
        output_dir = config.get("paths.output", "./output")
        cwd = os.path.abspath(output_dir)
    else:
        cwd = os.path.abspath(cwd)

    os.makedirs(cwd, exist_ok=True)
    agent_logger.debug(f"命令工作目录: {cwd}")

    # ============================================================
    # 第六层：执行命令
    # ============================================================
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            shell=False,
            cwd=cwd,
        )

        out = (result.stdout + result.stderr).strip()

        if result.returncode == 0:
            agent_logger.info(f"命令成功: {cmd[:50]}")
            return f"✅ {out}" if out else "✅ 命令执行成功（无输出）"
        else:
            agent_logger.warning(f"命令失败 (退出码 {result.returncode}): {cmd[:50]}")
            return f"❌ 命令失败 (退出码: {result.returncode})\n{out}" if out else f"❌ 命令失败 (退出码: {result.returncode})"

    except subprocess.TimeoutExpired:
        agent_logger.warning(f"命令超时 ({timeout}s): {cmd[:50]}")
        return f"⏰ 命令执行超时（{timeout}秒）"

    except FileNotFoundError:
        agent_logger.error(f"命令不存在: {executable}")
        return f"❌ 命令不存在: {executable}"

    except PermissionError:
        agent_logger.error(f"权限不足: {executable}")
        return f"❌ 权限不足: {executable}"

    except Exception as e:
        agent_logger.error(f"命令执行异常: {e}")
        return f"❌ 执行异常: {e}"


def get_current_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前日期和时间"""
    return datetime.now().strftime(format_str)


def get_current_date(_: str = "") -> str:
    """获取当前日期（YYYY-MM-DD）"""
    return datetime.now().strftime("%Y-%m-%d")


def get_timestamp(_: str = "") -> str:
    """获取Unix时间戳"""
    return str(int(datetime.now().timestamp()))


def register_command_tools():
    """注册命令工具"""
    tool_registry.register_tool(
        "run_command",
        run_command,
        "执行系统命令 (安全过滤，支持 pip/npm/git/python)"
    )
    tool_registry.register_tool(
        "get_time",
        get_current_time,
        "获取当前日期和时间"
    )
    tool_registry.register_tool(
        "get_date",
        get_current_date,
        "获取当前日期 (YYYY-MM-DD)"
    )
    tool_registry.register_tool(
        "get_timestamp",
        get_timestamp,
        "获取Unix时间戳"
    )
    print("  ✅ 命令工具: 4 (run_command/get_time/get_date/get_timestamp)")


# 自动注册
register_command_tools()