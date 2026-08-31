# core/ui.py
"""
进度反馈UI - 提供友好的交互反馈
"""

import time
import sys
from typing import Optional


class ProgressUI:
    """进度反馈UI"""

    _instance = None
    _spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    _spinner_idx = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def show_step(self, step_name: str, total: int, current: int,
                  extra: str = "") -> None:
        """显示进度条"""
        if total <= 0:
            return

        bar_length = 30
        progress = min(1.0, current / total)
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)

        line = f"\r  ⏳ {step_name} [{bar}] {progress * 100:.1f}%"
        if extra:
            line += f" {extra}"
        print(line, end="", flush=True)

    def show_thinking(self, model: str, message: str = "思考中...") -> None:
        """显示思考状态（带旋转动画）"""
        self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner)
        spinner = self._spinner[self._spinner_idx]
        print(f"\r  🧠 {model} {message} {spinner}", end="", flush=True)

    def show_loading(self, message: str) -> None:
        """显示加载状态（带旋转动画）"""
        self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner)
        spinner = self._spinner[self._spinner_idx]
        print(f"\r  ⏳ {message} {spinner}", end="", flush=True)

    def show_success(self, message: str) -> None:
        """显示成功"""
        print(f"\r  ✅ {message}")

    def show_error(self, message: str) -> None:
        """显示错误"""
        print(f"\r  ❌ {message}")

    def show_warning(self, message: str) -> None:
        """显示警告"""
        print(f"\r  ⚠️ {message}")

    def show_info(self, message: str) -> None:
        """显示信息"""
        print(f"\r  ℹ️ {message}")

    def show_result(self, message: str, result_type: str = "info") -> None:
        """显示结果"""
        prefix = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
        }.get(result_type, "•")
        print(f"\r  {prefix} {message}")

    def clear_line(self) -> None:
        """清除当前行"""
        print("\r" + " " * 80 + "\r", end="", flush=True)

    def newline(self) -> None:
        """换行"""
        print()

    def show_header(self, title: str, width: int = 60) -> None:
        """显示标题头"""
        print()
        print("=" * width)
        print(f"  {title}")
        print("=" * width)

    def show_footer(self, width: int = 60) -> None:
        """显示尾部"""
        print("=" * width)
        print()


# 全局UI实例
ui = ProgressUI()