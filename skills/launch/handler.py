# skills/launch/handler.py
"""
启动技能：打开电脑上的应用程序
使用 LLM 智能匹配应用名称和路径
"""

import os
import sys
import subprocess
import re
from typing import Optional, Tuple

from core.logger import agent_logger
from core.health import health_check
from models.manager import model_manager

# ============================================================
# 已知应用路径映射（作为 LLM 的参考，不是硬编码规则）
# ============================================================

KNOWN_PATHS = {
    # 系统工具（System32）
    "notepad.exe": "记事本",
    "calc.exe": "计算器",
    "mspaint.exe": "画图",
    "cmd.exe": "命令提示符",
    "powershell.exe": "PowerShell",
    "explorer.exe": "文件资源管理器",
    "taskmgr.exe": "任务管理器",
    "control.exe": "控制面板",

    # 常见应用（用户可能安装的位置）
    "msedge.exe": ["Edge浏览器", "Microsoft Edge"],
    "chrome.exe": ["Chrome浏览器", "Google Chrome"],
    "firefox.exe": ["Firefox浏览器", "火狐"],
    "Code.exe": ["VS Code", "VSCode", "Visual Studio Code"],
    "wechat.exe": ["微信", "WeChat"],
    "qq.exe": ["QQ"],
    "typora.exe": ["Typora", "Markdown编辑器"],
    "notepad++.exe": ["Notepad++", "记事本++"],
}


def _find_by_where(app_name: str) -> Optional[str]:
    """使用 where 命令查找"""
    try:
        result = subprocess.run(
            ['where', app_name],
            capture_output=True,
            text=True,
            timeout=3,
            shell=True
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines:
                return lines[0].strip()
    except Exception:
        pass
    return None


def _search_common_dirs(app_name: str) -> Optional[str]:
    """在常见目录中搜索"""
    common_dirs = [
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\Program Files\\Google\\Chrome\\Application",
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application",
        "C:\\Program Files\\Tencent\\WeChat",
        "C:\\Users\\{}\\AppData\\Local\\Programs\\Microsoft VS Code".format(os.getlogin()),
        "C:\\Users\\{}\\AppData\\Local\\Programs\\Typora".format(os.getlogin()),
        "C:\\Users\\{}\\AppData\\Local\\Programs\\Notepad++".format(os.getlogin()),
    ]

    candidates = [app_name]
    if not app_name.endswith('.exe'):
        candidates.append(f"{app_name}.exe")
    candidates.append(app_name.lower())
    candidates.append(app_name.capitalize())

    for base_dir in common_dirs:
        if not os.path.exists(base_dir):
            continue
        try:
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    if file.lower() in [c.lower() for c in candidates] or file.lower() == app_name.lower():
                        return os.path.join(root, file)
                    # 模糊匹配：文件名包含关键词
                    if len(app_name) > 3 and app_name.lower() in file.lower():
                        return os.path.join(root, file)
                # 限制深度
                depth = root.replace(base_dir, '').count(os.sep)
                if depth > 2:
                    break
        except Exception:
            continue
    return None


def _llm_find_app(user_input: str) -> Tuple[Optional[str], Optional[str]]:
    """
    使用 LLM 智能匹配应用
    返回: (应用名称, 建议路径)
    """
    model = model_manager.get_doer()
    if not model:
        return None, None

    prompt = f"""用户想要打开一个应用程序："{user_input}"

请根据用户描述，判断他想打开哪个应用，并给出可能的可执行文件名。

【规则】：
1. 只返回 JSON 格式
2. 格式：{{"app_name": "应用的真实名称", "exe_name": "可执行文件名", "common_paths": ["可能路径1", "可能路径2"]}}
3. 如果无法确定，返回 {{"app_name": "未知", "exe_name": "未知"}}

【已知映射】：
- 记事本 → notepad.exe
- 计算器 → calc.exe
- 画图 → mspaint.exe
- 命令提示符 → cmd.exe
- PowerShell → powershell.exe
- 文件资源管理器 → explorer.exe
- Edge浏览器 → msedge.exe
- Chrome浏览器 → chrome.exe
- VS Code → Code.exe
- 微信 → wechat.exe

【用户输入】：{user_input}

【返回 JSON】："""

    result, error = health_check.safe_call(model.invoke, prompt, max_retries=1)

    if error or not result:
        return None, None

    try:
        import json
        # 提取 JSON
        content = result.content
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            app_name = data.get("app_name")
            exe_name = data.get("exe_name")
            common_paths = data.get("common_paths", [])

            # 如果有路径，直接返回
            for path in common_paths:
                if os.path.exists(path):
                    return app_name, path

            # 尝试用 where 查找 exe_name
            if exe_name and exe_name != "未知":
                found = _find_by_where(exe_name)
                if found:
                    return app_name, found

                # 尝试搜索常见目录
                found = _search_common_dirs(exe_name)
                if found:
                    return app_name, found

                # 返回 exe_name 让 run_command 尝试
                return app_name, exe_name

            return app_name, None
    except Exception as e:
        agent_logger.warning(f"LLM 解析失败: {e}")

    return None, None


def handler(context) -> str:
    """启动技能实现"""
    agent_logger.info(f"执行启动技能: {context.user_input[:50]}...")

    # 提取应用名称（去掉路由符号）
    user_input = context.user_input
    user_input = re.sub(r'^[\[【(（]\s*', '', user_input)
    user_input = re.sub(r'[\】】)）]\s*$', '', user_input)

    # 去掉触发词
    triggers = ["打开", "启动", "运行", "开启"]
    for trigger in triggers:
        if user_input.startswith(trigger):
            user_input = user_input[len(trigger):].strip()
            break

    if not user_input:
        return "❌ 请指定要打开的应用名称"

    agent_logger.info(f"用户想打开: {user_input}")

    # ============================================================
    # 1. 先用 LLM 匹配
    # ============================================================
    app_name, app_path = _llm_find_app(user_input)

    if app_path and os.path.exists(app_path):
        agent_logger.info(f"✅ LLM 找到应用: {app_name} → {app_path}")
        return _launch_app(app_path, app_name or user_input)

    if app_name and app_path:
        # 尝试用 run_command 执行（可能是系统命令）
        agent_logger.info(f"尝试执行: {app_path}")
        from tools.registry import tool_registry
        result = tool_registry.execute("run_command", command=app_path)
        if "❌" not in result:
            return f"✅ 已打开: {app_name or user_input}"

    # ============================================================
    # 2. 尝试用 where 命令查找
    # ============================================================
    for name in [user_input, user_input + ".exe"]:
        found = _find_by_where(name)
        if found:
            agent_logger.info(f"✅ where 找到: {found}")
            return _launch_app(found, user_input)

    # ============================================================
    # 3. 尝试在常见目录搜索
    # ============================================================
    found = _search_common_dirs(user_input)
    if found:
        agent_logger.info(f"✅ 搜索找到: {found}")
        return _launch_app(found, user_input)

    # ============================================================
    # 4. 最后尝试用 start 命令
    # ============================================================
    if sys.platform == 'win32':
        result = tool_registry.execute("run_command", command=f"start {user_input}")
        if "❌" not in result:
            return f"✅ 已尝试打开: {user_input}"

    return f"❌ 找不到应用: {user_input}"


def _launch_app(app_path: str, display_name: str) -> str:
    """启动应用"""
    try:
        if sys.platform == 'win32':
            if os.path.exists(app_path) and app_path.endswith('.exe'):
                subprocess.Popen([app_path], shell=True)
                return f"✅ 已打开: {display_name}"
            else:
                subprocess.Popen(f'start {app_path}', shell=True)
                return f"✅ 已打开: {display_name}"
        else:
            subprocess.Popen([app_path], shell=True)
            return f"✅ 已打开: {display_name}"
    except Exception as e:
        return f"❌ 启动失败: {e}"