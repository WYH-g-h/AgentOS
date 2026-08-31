# core/parser.py
"""
统一解析器：从 LLM 输出中解析 FILE/CONTENT/CMD
"""

import re
from typing import Dict, List


def parse_files(text: str) -> Dict[str, str]:
    """
    从文本中解析 FILE: 和 CONTENT:

    格式:
        FILE: filename
        CONTENT:
        文件内容
        多行
        ENDCONTENT

    Args:
        text: LLM 输出的文本

    Returns:
        Dict[str, str]: {文件名: 内容}
    """
    if not text:
        return {}

    files = {}
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 匹配 FILE: 或 【文件】
        if re.match(r'^(?:FILE:|【文件】)\s*(.+)', line, re.IGNORECASE):
            fp = re.sub(r'^(?:FILE:|【文件】)\s*', '', line, flags=re.IGNORECASE).strip()
            if not fp:
                i += 1
                continue

            i += 1
            content_lines = []
            found_end = False

            while i < len(lines):
                cline = lines[i].strip()

                # 检查结束标记
                if re.match(r'^(?:CONTENT:|内容:|ENDCONTENT|FILE:|MODIFY:|CMD:)', cline, re.IGNORECASE):
                    # 如果这一行本身就是 CONTENT: 开头，提取后面的内容
                    if re.match(r'^(?:CONTENT:|内容:)', cline, re.IGNORECASE):
                        rest = re.sub(r'^(?:CONTENT:|内容:)', '', cline, flags=re.IGNORECASE).strip()
                        if rest:
                            content_lines.append(rest)
                        i += 1
                        continue
                    else:
                        found_end = True
                        break

                # 普通内容行
                if cline or content_lines:
                    content_lines.append(lines[i])
                i += 1

            # 如果没遇到 ENDCONTENT，回退到上一个位置
            if not found_end and content_lines:
                # 继续解析，但保留内容
                pass

            content = "\n".join(content_lines).strip()

            # 清理 markdown 代码块
            if content.startswith("```"):
                content = "\n".join(content.split("\n")[1:])
            if content.endswith("```"):
                content = content[:-3].strip()

            if content and len(content.strip()) >= 5:
                files[fp] = content
            continue

        i += 1

    return files


def parse_commands(text: str) -> List[str]:
    """
    从文本中解析 CMD:

    Args:
        text: LLM 输出的文本

    Returns:
        List[str]: 命令列表
    """
    if not text:
        return []

    commands = []
    for line in text.split("\n"):
        match = re.match(r'^(?:CMD:|【命令】)\s*(.+)', line, re.IGNORECASE)
        if match:
            cmd = match.group(1).strip()
            if cmd:
                # 过滤简单命令
                if not any(cmd.startswith(p) for p in ["git ", "cd ", "dir", "ls ", "pwd"]):
                    commands.append(cmd)

    return commands


def parse_modify(text: str) -> Dict[str, str]:
    """
    解析 MODIFY: 格式（修改专用）

    Args:
        text: LLM 输出的文本

    Returns:
        Dict[str, str]: {文件名: 内容}
    """
    if not text:
        return {}

    files = {}
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if re.match(r'^(?:MODIFY:|【修改】)\s*(.+)', line, re.IGNORECASE):
            fp = re.sub(r'^(?:MODIFY:|【修改】)\s*', '', line, flags=re.IGNORECASE).strip()
            if not fp:
                i += 1
                continue

            i += 1
            content_lines = []

            while i < len(lines):
                cline = lines[i].strip()
                if re.match(r'^(?:CONTENT:|内容:|ENDCONTENT|MODIFY:|FILE:|CMD:)', cline, re.IGNORECASE):
                    if re.match(r'^(?:CONTENT:|内容:)', cline, re.IGNORECASE):
                        rest = re.sub(r'^(?:CONTENT:|内容:)', '', cline, flags=re.IGNORECASE).strip()
                        if rest:
                            content_lines.append(rest)
                        i += 1
                        continue
                    else:
                        break

                if cline or content_lines:
                    content_lines.append(lines[i])
                i += 1

            content = "\n".join(content_lines).strip()
            if content.startswith("```"):
                content = "\n".join(content.split("\n")[1:])
            if content.endswith("```"):
                content = content[:-3].strip()

            if content and len(content.strip()) >= 5:
                files[fp] = content
            continue

        i += 1

    return files


def extract_filename(text: str) -> str:
    """
    从文本中提取文件名

    Args:
        text: 用户输入或LLM输出

    Returns:
        str: 提取的文件名，如果没有则返回空字符串
    """
    patterns = [
        r'([a-zA-Z0-9_\-\.]+\.(?:html|py|js|css|json|txt|md|xml|yaml|yml|toml|ini|conf|cfg))',
        r'([a-zA-Z0-9_\-\.]+\.\w+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            filename = match.group(1)
            # 清理可能的非文件字符
            filename = re.sub(r'[^\w\.\-]', '', filename)
            return filename

    return ""