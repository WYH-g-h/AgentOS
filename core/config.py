# core/config.py
"""
配置管理：支持YAML加载、环境变量覆盖、热加载、线程安全
"""

import os
import yaml
import threading
from pathlib import Path
from typing import Any, Dict, Optional, List

from .paths import get_config_dir, ensure_directories


class Config:
    """配置管理器 - 单例模式，支持热加载，线程安全"""

    _instance = None
    _config: Dict[str, Any] = {}
    _config_dir: Path = None
    _loaded_files: List[str] = []
    _lock = threading.RLock()
    _version = "1.0.0"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config_dir = get_config_dir()
            cls._instance._load_defaults()
            ensure_directories()
        return cls._instance

    def _load_defaults(self):
        """加载所有配置文件"""
        with self._lock:
            self._config = {}
            self._loaded_files = []

            config_files = [
                "default.yaml",
                "models.yaml",
                "tools.yaml",
            ]

            for filename in config_files:
                filepath = self._config_dir / filename
                if filepath.exists():
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = yaml.safe_load(f) or {}
                            self._merge_config(data)
                            self._loaded_files.append(filename)
                    except Exception as e:
                        print(f"⚠️ 加载配置失败 {filename}: {e}")

            self._load_from_env()

    def _merge_config(self, data: Dict, depth: int = 0):
        """深度合并配置"""
        if depth > 10:
            return

        for key, value in data.items():
            if key in self._config and isinstance(self._config[key], dict) and isinstance(value, dict):
                self._merge_dict(self._config[key], value, depth + 1)
            else:
                self._config[key] = value

    def _merge_dict(self, target: Dict, source: Dict, depth: int = 0):
        """合并字典"""
        if depth > 10:
            return

        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_dict(target[key], value, depth + 1)
            else:
                target[key] = value

    def _load_from_env(self):
        """从环境变量加载配置"""
        mappings = {
            "OLLAMA_BASE_URL": ("ollama", "base_url"),
            "OLLAMA_GPU_OVERHEAD": ("ollama", "gpu_overhead"),
            "OLLAMA_NUM_PARALLEL": ("ollama", "num_parallel"),
            "THINKER_MODEL": ("models", "thinker"),
            "DOER_MODEL": ("models", "doer"),
            "ROUTER_MODEL": ("models", "router"),
            "OPENAI_API_KEY": ("providers", "openai", "api_key"),
            "DEEPSEEK_API_KEY": ("providers", "deepseek", "api_key"),
        }

        for env_var, keys in mappings.items():
            value = os.getenv(env_var)
            if value:
                target = self._config
                for key in keys[:-1]:
                    if key not in target:
                        target[key] = {}
                    target = target[key]
                target[keys[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持点号分隔）"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """设置配置值"""
        with self._lock:
            keys = key.split(".")
            target = self._config
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = value

    def save(self):
        """保存配置到文件"""
        try:
            # 确保配置目录存在
            self._config_dir.mkdir(parents=True, exist_ok=True)

            # 保存到 default.yaml
            filepath = self._config_dir / "default.yaml"

            # 读取现有配置（保留注释）
            existing_data = {}
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = yaml.safe_load(f) or {}

            # 合并更新
            existing_data.update(self._config)

            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(existing_data, f, allow_unicode=True, default_flow_style=False)

            print(f"✅ 配置已保存: {filepath}")
            return True
        except Exception as e:
            print(f"❌ 保存配置失败: {e}")
            return False

    def get_all(self) -> Dict[str, Any]:
        """获取全部配置"""
        with self._lock:
            return self._config.copy()

    def reload(self):
        """重新加载配置"""
        with self._lock:
            print("🔄 重新加载配置...")
            self._config = {}
            self._load_defaults()
            print(f"✅ 配置已重新加载 ({len(self._loaded_files)} 个文件)")

    def enable_hot_reload(self):
        """启用热加载"""
        try:
            import watchfiles

            def on_change(changes):
                print(f"🔄 检测到配置变化: {changes}")
                self.reload()

            import threading
            def watcher_thread():
                for changes in watchfiles.watch(self._config_dir):
                    on_change(changes)

            thread = threading.Thread(target=watcher_thread, daemon=True)
            thread.start()
            print("✅ 配置热加载已启用")
        except ImportError:
            print("⚠️ watchfiles 未安装，热加载不可用")

    def validate(self) -> List[str]:
        """验证配置"""
        errors = []

        from models.registry import model_registry

        if not model_registry.get_thinker():
            errors.append("缺少 thinker 模型配置")

        if not model_registry.get_doer():
            errors.append("缺少 doer 模型配置")

        if not model_registry.get_router():
            errors.append("缺少 router 模型配置")

        if not self.get("ollama.base_url"):
            errors.append("缺少 ollama.base_url 配置")

        from .paths import get_output_dir, get_memory_dir, get_rag_dir, get_state_dir, get_logs_dir, get_skills_dir, \
            get_workflows_dir
        required_dirs = [
            ("paths.output", get_output_dir()),
            ("paths.memory", get_memory_dir()),
            ("paths.rag", get_rag_dir()),
            ("paths.state", get_state_dir()),
            ("paths.logs", get_logs_dir()),
            ("paths.skills", get_skills_dir()),
            ("paths.workflows", get_workflows_dir()),
        ]

        for key, path in required_dirs:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建目录 {path}: {e}")

        return errors


# 全局配置实例
config = Config()