# core/checker.py
"""
执行检查器：验证文件、命令执行结果
支持 Python/JSON/HTML/JavaScript/CSS/Markdown/YAML 等多种格式
"""

import os
import json
import ast
import re
from typing import Tuple, Optional, List
from pathlib import Path

from core.config import config
from core.logger import agent_logger


class ExecutionChecker:
    """
    执行结果检查器
    提供文件验证、命令结果验证等功能
    """

    OUTPUT_DIR = config.get("paths.output", "./output")

    @classmethod
    def check_file(cls, filepath: str, content: Optional[str] = None) -> Tuple[bool, str, str]:
        """
        验证文件

        Args:
            filepath: 文件路径（相对于 OUTPUT_DIR）
            content: 文件内容（如果提供，则验证内容而不是读取文件）

        Returns:
            Tuple[bool, str, str]: (是否通过, 消息, 详情)
        """
        if not filepath:
            return False, "❌ 文件路径为空", ""

        filepath = filepath.replace("\\", "/").lstrip("./")
        full_path = os.path.join(cls.OUTPUT_DIR, filepath)

        if content is not None:
            return cls._verify_content(filepath, content)

        if not os.path.exists(full_path):
            return False, "❌ 文件不存在", full_path

        if os.path.getsize(full_path) == 0:
            return False, "❌ 文件为空", full_path

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return False, f"❌ 读取失败: {e}", str(e)

        return cls._verify_content(filepath, content)

    @classmethod
    def _verify_content(cls, filepath: str, content: str) -> Tuple[bool, str, str]:
        """验证文件内容"""
        if not content or len(content.strip()) < 5:
            return False, "❌ 内容为空或太短", f"长度: {len(content)}"

        filepath_lower = filepath.lower()

        # Python
        if filepath_lower.endswith('.py'):
            try:
                ast.parse(content)
                return True, "✅ Python语法正确", ""
            except SyntaxError as e:
                return False, f"❌ Python语法错误", f"行 {e.lineno}: {e.msg}"
            except Exception as e:
                return False, f"❌ Python验证失败", str(e)

        # JSON
        if filepath_lower.endswith('.json'):
            try:
                json.loads(content)
                return True, "✅ JSON格式正确", ""
            except json.JSONDecodeError as e:
                return False, f"❌ JSON格式错误", f"行 {e.lineno}: {e.msg}"

        # HTML
        if filepath_lower.endswith('.html'):
            content_lower = content.lower()
            issues = []
            if '<!DOCTYPE html' not in content_lower and '<html' not in content_lower:
                issues.append("缺少 <!DOCTYPE html> 或 <html>")
            if '</html>' not in content_lower:
                issues.append("缺少 </html>")
            if '<head' not in content_lower:
                issues.append("缺少 <head>")
            if '<body' not in content_lower:
                issues.append("缺少 <body>")
            if issues:
                return False, "⚠️ HTML结构问题", "; ".join(issues[:3])
            return True, "✅ HTML结构完整", ""

        # JavaScript
        if filepath_lower.endswith('.js'):
            issues = []
            js_keywords = ['function', 'const', 'let', 'var', 'return', 'console', 'export', 'import']
            if not any(kw in content for kw in js_keywords):
                issues.append("可能不是有效的JS文件")
            open_paren = content.count('(') - content.count(')')
            open_brace = content.count('{') - content.count('}')
            if open_paren != 0:
                issues.append(f"括号不匹配: {open_paren}")
            if open_brace != 0:
                issues.append(f"花括号不匹配: {open_brace}")
            if issues:
                return False, "⚠️ JS语法问题", "; ".join(issues[:3])
            return True, "✅ JS文件检查通过", ""

        # CSS
        if filepath_lower.endswith('.css'):
            if '{' not in content or '}' not in content:
                return False, "⚠️ CSS缺少选择器", "需要包含 { 和 }"
            css_patterns = [r'[a-zA-Z-]+\s*:\s*[^;]+;', r'@media', r'@keyframes']
            if not any(re.search(p, content) for p in css_patterns):
                return False, "⚠️ CSS可能无效", "未找到有效的CSS属性"
            return True, "✅ CSS文件检查通过", ""

        # Markdown
        if filepath_lower.endswith('.md'):
            if len(content.strip()) < 10:
                return False, "⚠️ Markdown内容太短", ""
            if not re.search(r'^#{1,6}\s+', content, re.MULTILINE):
                return True, "✅ Markdown文件存在（建议添加标题）", ""
            return True, "✅ Markdown文件检查通过", ""

        # YAML
        if filepath_lower.endswith(('.yaml', '.yml')):
            try:
                import yaml
                yaml.safe_load(content)
                return True, "✅ YAML格式正确", ""
            except Exception as e:
                return False, f"❌ YAML格式错误", str(e)

        if len(content.strip()) >= 10:
            return True, "✅ 文件存在", f"大小: {len(content)} 字符"
        return True, "✅ 验证通过", ""

    @classmethod
    def check_command_result(cls, result: str) -> Tuple[bool, str]:
        """验证命令执行结果"""
        if not result:
            return False, "无结果"
        if "✅" in result:
            return True, result
        if "❌" in result or "⏰" in result:
            return False, result
        error_keywords = ["error", "Error", "ERROR", "fail", "Fail", "FAIL", "exception"]
        for kw in error_keywords:
            if kw in result:
                return False, result
        return True, result

    @classmethod
    def check_multiple_files(cls, files: List[str]) -> dict:
        """批量验证多个文件"""
        results = {}
        for filepath in files:
            results[filepath] = cls.check_file(filepath)
        return results

    @classmethod
    def get_file_issues(cls, filepath: str) -> List[str]:
        """获取文件的问题列表"""
        ok, msg, detail = cls.check_file(filepath)
        if ok:
            return []
        issues = []
        if msg:
            issues.append(msg)
        if detail:
            issues.append(detail)
        return issues


checker = ExecutionChecker()