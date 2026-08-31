# core/logger.py
"""
结构化日志系统：支持控制台、文件、JSON审计日志、日志轮转
支持配置驱动级别
"""

import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from logging.handlers import RotatingFileHandler

from core.config import config
from core.paths import get_logs_dir


class AgentLogger:
    """
    结构化日志系统

    日志级别（由低到高）:
    DEBUG < INFO < WARNING < ERROR < CRITICAL

    输出目标:
    - 控制台: 用户交互 (默认 INFO)
    - 文件:   完整日志 (默认 DEBUG)
    - 审计:   操作记录 (默认 INFO)
    """

    _instance = None

    def __new__(cls, log_dir: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir: Optional[str] = None):
        if self._initialized:
            return

        # ✅ 使用统一路径
        if log_dir is None:
            log_dir = str(get_logs_dir())

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 日志文件
        self.log_file = self.log_dir / "agent.log"
        self.audit_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"

        # 读取配置
        self._load_config()

        # 设置 logging
        self._setup_logging()
        self._initialized = True

    def _load_config(self):
        """从配置加载日志级别"""
        logging_config = config.get("logging", {})

        # 级别映射
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        # 读取配置，默认值
        console_level_name = logging_config.get("console_level", "INFO").upper()
        file_level_name = logging_config.get("file_level", "DEBUG").upper()
        audit_level_name = logging_config.get("audit_level", "INFO").upper()

        self.console_level = level_map.get(console_level_name, logging.INFO)
        self.file_level = level_map.get(file_level_name, logging.DEBUG)
        self.audit_level = level_map.get(audit_level_name, logging.INFO)

        # 配置审计日志记录级别
        self.audit_levels = {
            "DEBUG": ["debug"],
            "INFO": ["info", "debug"],
            "WARNING": ["warning", "info", "debug"],
            "ERROR": ["error", "warning", "info", "debug"],
        }.get(audit_level_name.upper(), ["info", "warning", "error"])

        # 文件轮转配置
        self.max_bytes = logging_config.get("max_size", 10) * 1024 * 1024
        self.backup_count = logging_config.get("backup_count", 5)

    def _setup_logging(self):
        self.logger = logging.getLogger("AgentOS")
        self.logger.setLevel(logging.DEBUG)  # 根级别设为最低
        self.logger.handlers.clear()

        # ============================================================
        # 1. 控制台输出 - 用户交互
        # ============================================================
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(self.console_level)
        console.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(console)

        # ============================================================
        # 2. 文件日志 - 完整记录
        # ============================================================
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.file_level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(file_handler)

        # ============================================================
        # 3. 启用行缓冲（兼容处理）
        # ============================================================
        try:
            sys.stdout.reconfigure(line_buffering=True)
        except (AttributeError, ValueError):
            # Python < 3.7 或环境不支持
            pass

    def _should_audit(self, level: str) -> bool:
        """判断是否应该写入审计日志"""
        return level in self.audit_levels

    def _write_audit(self, level: str, message: str, data: Dict[str, Any]):
        """写入审计日志（JSONL格式）"""
        if not self._should_audit(level):
            return

        try:
            with open(self.audit_file, 'a', encoding='utf-8') as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "level": level,
                    "message": message,
                    **data
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            self.logger.warning(f"审计日志写入失败: {e}")

    def debug(self, message: str, **kwargs):
        """调试日志 - 写入文件（如果配置），不写入控制台"""
        self.logger.debug(message)
        if self._should_audit("debug"):
            self._write_audit("debug", message, kwargs)

    def info(self, message: str, **kwargs):
        """信息日志 - 控制台显示，写入审计"""
        self.logger.info(message)
        if self._should_audit("info"):
            self._write_audit("info", message, kwargs)

    def warning(self, message: str, **kwargs):
        """警告日志 - 控制台显示，写入文件和审计"""
        self.logger.warning(message)
        if self._should_audit("warning"):
            self._write_audit("warning", message, kwargs)

    def error(self, message: str, **kwargs):
        """错误日志 - 控制台显示，写入文件和审计"""
        self.logger.error(message)
        if self._should_audit("error"):
            self._write_audit("error", message, kwargs)

    def critical(self, message: str, **kwargs):
        """严重错误日志"""
        self.logger.critical(message)
        if self._should_audit("critical"):
            self._write_audit("critical", message, kwargs)

    def event(self, event_type: str, **kwargs):
        """事件日志（结构化）"""
        message = f"[{event_type}]"
        self.logger.info(message)
        if self._should_audit("info"):
            self._write_audit("event", event_type, kwargs)

    def flush(self):
        """强制刷新所有日志处理器"""
        for handler in self.logger.handlers:
            try:
                handler.flush()
            except Exception:
                pass
        try:
            sys.stdout.flush()
        except Exception:
            pass

    def set_level(self, level_name: str, target: str = "console"):
        """
        动态调整日志级别

        Args:
            level_name: DEBUG, INFO, WARNING, ERROR, CRITICAL
            target: console, file, audit
        """
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        level = level_map.get(level_name.upper(), logging.INFO)

        if target == "console":
            self.console_level = level
            for handler in self.logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(level)
        elif target == "file":
            self.file_level = level
            for handler in self.logger.handlers:
                if isinstance(handler, RotatingFileHandler):
                    handler.setLevel(level)
        elif target == "audit":
            self.audit_level = level
            # 更新审计级别列表
            self.audit_levels = {
                "DEBUG": ["debug"],
                "INFO": ["info", "debug"],
                "WARNING": ["warning", "info", "debug"],
                "ERROR": ["error", "warning", "info", "debug"],
            }.get(level_name.upper(), ["info", "warning", "error"])


# 全局日志实例
agent_logger = AgentLogger()