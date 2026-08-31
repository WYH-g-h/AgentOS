# core/paths.py
"""
统一路径管理 - 兼容开发环境和打包环境
数据存储在用户目录，配置文件在程序目录
"""

import sys
import os
from pathlib import Path
import io


def is_frozen() -> bool:
    """检测是否在 PyInstaller 打包环境中"""
    return getattr(sys, 'frozen', False)


def get_project_root() -> Path:
    """获取项目根目录（开发环境）或程序安装目录（打包环境）"""
    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def get_app_data_dir() -> Path:
    """
    获取应用数据目录（用户数据）
    开发环境：项目根目录/data
    打包环境：优先 resources/data，如果不存在则使用 AppData
    """
    if is_frozen():
        # ✅ 优先使用 resources/data
        resources_data = Path(sys.executable).parent / "resources" / "data"
        if resources_data.exists():
            return resources_data

        # 如果 resources/data 不存在，回退到 AppData
        if sys.platform == 'win32':
            base = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming'))
        elif sys.platform == 'darwin':
            base = Path.home() / 'Library/Application Support'
        else:
            base = Path.home() / '.config'
        return base / "AgentOS"

    return get_project_root() / "data"


def get_config_dir() -> Path:
    """获取配置目录"""
    if is_frozen():
        # 从程序目录读取配置
        return get_project_root() / "config"
    return get_project_root() / "config"


def get_skills_dir() -> Path:
    """获取技能目录"""
    if is_frozen():
        return get_project_root() / "skills"
    return get_project_root() / "skills"


def get_workflows_dir() -> Path:
    """获取工作流目录"""
    if is_frozen():
        return get_project_root() / "workflows"
    return get_project_root() / "workflows"


def get_output_dir() -> Path:
    """获取输出目录（用户数据）"""
    if is_frozen():
        return get_app_data_dir() / "output"
    return get_project_root() / "output"


def get_uploads_dir() -> Path:
    """获取上传目录（已废弃，使用 output）"""
    return get_output_dir()


def get_logs_dir() -> Path:
    """获取日志目录"""
    return get_app_data_dir() / "logs"


def get_memory_dir() -> Path:
    """获取记忆目录"""
    return get_app_data_dir() / "chats"


def get_rag_dir() -> Path:
    """获取RAG目录"""
    return get_app_data_dir() / "rag"


def get_state_dir() -> Path:
    """获取状态目录"""
    return get_app_data_dir() / "state"


def get_unified_memory_dir() -> Path:
    """获取统一记忆目录"""
    return get_app_data_dir() / "unified_memory"


def ensure_directories():
    """确保所有必要目录存在"""
    dirs = [
        get_app_data_dir(),
        get_output_dir(),
        get_logs_dir(),
        get_memory_dir(),
        get_rag_dir(),
        get_state_dir(),
        get_unified_memory_dir(),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ 目录: {d}")


# 全局实例
PROJECT_ROOT = get_project_root()
APP_DATA_DIR = get_app_data_dir()