# skills/loader.py
"""
技能加载器：从文件夹加载技能配置和实现
增强: 提示词与技能捆绑
"""

import os
import yaml
import importlib.util
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any

from .base import SkillSpec
from .registry import skill_registry
from core.logger import agent_logger
from core.prompts import prompt_manager, PromptTemplate

REQUIRED_FIELDS = ["name", "description", "tools"]
OPTIONAL_FIELDS = ["version", "category", "model", "timeout", "retries", "triggers", "enabled", "prompt"]


def validate_skill_config(config: dict, skill_path: str) -> List[str]:
    """验证技能配置"""
    errors = []

    for field in REQUIRED_FIELDS:
        if field not in config or config[field] is None:
            errors.append(f"缺少必填字段: {field}")
        elif field == "tools" and not isinstance(config["tools"], list):
            errors.append("tools 必须是列表")

    if "tools" in config and config["tools"] is not None:
        if not isinstance(config["tools"], list):
            errors.append("tools 必须是列表")

    if "triggers" in config and config["triggers"] is not None:
        if not isinstance(config["triggers"], list):
            errors.append("triggers 必须是列表")

    if "timeout" in config:
        try:
            int(config["timeout"])
        except (ValueError, TypeError):
            errors.append("timeout 必须是数字")

    if "retries" in config:
        try:
            int(config["retries"])
        except (ValueError, TypeError):
            errors.append("retries 必须是数字")

    return errors


def load_skill(skill_dir: str) -> Optional[SkillSpec]:
    """加载单个技能 - 包含提示词"""
    skill_path = Path(skill_dir)

    config_file = skill_path / "skill.yaml"
    if not config_file.exists():
        agent_logger.warning(f"技能配置不存在: {config_file}")
        return None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        agent_logger.error(f"加载技能配置失败: {config_file}: {e}")
        return None

    errors = validate_skill_config(config, str(skill_path))
    if errors:
        agent_logger.error(f"技能配置验证失败 {skill_path.name}:")
        for error in errors:
            agent_logger.error(f"  - {error}")
        return None

    spec = SkillSpec(
        name=config.get("name", skill_path.name),
        description=config.get("description", ""),
        version=config.get("version", "1.0"),
        category=config.get("category", "general"),
        tools=config.get("tools", []),
        model=config.get("model"),
        timeout=config.get("timeout", 60),
        retries=config.get("retries", 2),
        triggers=config.get("triggers", []),
        enabled=config.get("enabled", True),
        path=str(skill_path),
    )

    # 存储提示词配置
    prompt_config = config.get("prompt", {})
    if prompt_config:
        spec.prompt = prompt_config.get("template", "")
        spec.prompt_vars = prompt_config.get("variables", {})

    # 注册提示词到 prompt_manager
    if spec.prompt:
        prompt_template = PromptTemplate(
            system=spec.prompt.get("system", ""),
            user=spec.prompt.get("user", ""),
            version=spec.version,
            description=spec.description
        )
        prompt_manager.register(f"skill_{spec.name}", prompt_template)
        agent_logger.debug(f"✅ 注册提示词: skill_{spec.name}")

    handler_file = skill_path / "handler.py"
    if handler_file.exists():
        handler = _load_handler(handler_file, spec.name)
        if handler:
            skill_registry.register_skill(spec, handler)
            agent_logger.info(f"✅ 加载技能: {spec.name}")
            return spec

    agent_logger.warning(f"技能 {spec.name} 缺少处理器: {handler_file}")
    return None


def _load_handler(handler_file: Path, skill_name: str) -> Optional[Callable]:
    """动态加载处理器"""
    try:
        spec = importlib.util.spec_from_file_location(
            f"skills.{skill_name}.handler",
            handler_file
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "handler"):
            return module.handler
        else:
            agent_logger.warning(f"处理器缺少 handler 函数: {skill_name}")
            return None
    except Exception as e:
        agent_logger.error(f"加载处理器失败 {skill_name}: {e}")
        return None


def load_skills(skills_dir: str = "./skills"):
    """加载 skills 目录中的所有技能"""
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        agent_logger.warning(f"技能目录不存在: {skills_dir}")
        return

    loaded = 0
    for skill_dir in skills_path.iterdir():
        if skill_dir.is_dir() and skill_dir.name != "__pycache__" and not skill_dir.name.startswith("."):
            config_file = skill_dir / "skill.yaml"
            if config_file.exists():
                spec = load_skill(str(skill_dir))
                if spec:
                    loaded += 1

    agent_logger.info(f"✅ 加载了 {loaded} 个技能")

    # 刷新路由映射（支持热加载）
    try:
        from core.router import router
        router.refresh_route_map()
        agent_logger.info(f"✅ 路由映射已刷新（{len(router._route_map)} 条）")
    except Exception as e:
        agent_logger.warning(f"刷新路由映射失败: {e}")


def reload_skill(skill_name: str):
    """重新加载单个技能"""
    skill_registry.remove(skill_name)
    skill_registry._handlers.pop(skill_name, None)

    skills_dir = Path("./skills")
    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir() and skill_dir.name == skill_name:
            load_skill(str(skill_dir))
            break

    # 刷新路由映射
    try:
        from core.router import router
        router.refresh_route_map()
        agent_logger.info(f"✅ 路由映射已刷新（{len(router._route_map)} 条）")
    except Exception as e:
        agent_logger.warning(f"刷新路由映射失败: {e}")