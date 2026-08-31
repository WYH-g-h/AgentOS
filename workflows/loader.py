# workflows/loader.py
"""
工作流加载器：从文件夹加载工作流配置
增强: 提示词与工作流捆绑 + 模型配置
"""

import yaml
from pathlib import Path
from typing import Optional, List, Set, Dict

from .base import WorkflowSpec, WorkflowStep
from .registry import workflow_registry
from core.logger import agent_logger
from core.prompts import prompt_manager, PromptTemplate


def validate_step(step_data: dict, index: int) -> List[str]:
    """验证工作流步骤"""
    errors = []

    name = step_data.get("name", "")
    if not name:
        errors.append(f"步骤 {index}: 缺少 name")

    skill = step_data.get("skill", "")
    if not skill:
        errors.append(f"步骤 {index}: 缺少 skill")

    return errors


def detect_cycle(steps: List[WorkflowStep]) -> Optional[List[str]]:
    """
    检测循环依赖
    返回循环路径，如果没有循环返回 None
    """
    graph: Dict[str, Set[str]] = {}
    for step in steps:
        graph[step.name] = set(step.depends_on or [])

    visited = set()
    path = []

    def dfs(node: str) -> bool:
        if node in path:
            return True
        if node in visited:
            return False

        visited.add(node)
        path.append(node)

        for dep in graph.get(node, []):
            if dep in graph:
                if dfs(dep):
                    return True

        path.pop()
        return False

    for node in graph:
        if node not in visited:
            if dfs(node):
                return path + [node]

    return None


def load_workflow(workflow_dir: str) -> Optional[WorkflowSpec]:
    """加载单个工作流 - 包含提示词和模型配置"""
    workflow_path = Path(workflow_dir)

    config_file = workflow_path / "workflow.yaml"
    if not config_file.exists():
        agent_logger.warning(f"工作流配置不存在: {config_file}")
        return None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        agent_logger.error(f"加载工作流配置失败: {config_file}: {e}")
        return None

    steps_file = workflow_path / "steps.yaml"
    steps_config = []
    if steps_file.exists():
        try:
            with open(steps_file, 'r', encoding='utf-8') as f:
                steps_config = yaml.safe_load(f) or []
        except Exception as e:
            agent_logger.error(f"加载步骤配置失败: {steps_file}: {e}")

    validated_steps = []
    for idx, step_data in enumerate(steps_config):
        errors = validate_step(step_data, idx)
        if errors:
            agent_logger.error(f"工作流 {workflow_path.name} 步骤验证失败:")
            for error in errors:
                agent_logger.error(f"  - {error}")
            return None

        step = WorkflowStep(
            name=step_data.get("name", ""),
            skill=step_data.get("skill", ""),
            params=step_data.get("params", {}),
            depends_on=step_data.get("depends_on", []),
            condition=step_data.get("condition"),
        )
        validated_steps.append(step)

    # 检测循环依赖
    cycle = detect_cycle(validated_steps)
    if cycle:
        agent_logger.error(f"工作流 {workflow_path.name} 存在循环依赖: {' → '.join(cycle)}")
        return None

    spec = WorkflowSpec(
        name=config.get("name", workflow_path.name),
        description=config.get("description", ""),
        steps=validated_steps,
        version=config.get("version", "1.0"),
        enabled=config.get("enabled", True),
        triggers=config.get("triggers", []),
        config=config.get("config", {}),
        path=str(workflow_path),
    )

    # 存储提示词配置
    prompt_config = config.get("prompt", {})
    if prompt_config:
        spec.prompt = prompt_config.get("template", "")
        spec.prompt_vars = prompt_config.get("variables", {})

    # 存储模型配置
    model_config = config.get("model", {})
    if model_config:
        spec.model = model_config.get("name")
        spec.model_config = model_config

    # 注册提示词到 prompt_manager
    if spec.prompt:
        prompt_template = PromptTemplate(
            system=spec.prompt.get("system", ""),
            user=spec.prompt.get("user", ""),
            version=spec.version,
            description=spec.description
        )
        prompt_manager.register(f"workflow_{spec.name}", prompt_template)
        agent_logger.debug(f"✅ 注册提示词: workflow_{spec.name}")

    workflow_registry.register(spec.name, spec)
    agent_logger.info(f"✅ 加载工作流: {spec.name} ({len(spec.steps)} 步)")
    return spec


def load_workflows(workflows_dir: str = "./workflows"):
    workflows_path = Path(workflows_dir)
    if not workflows_path.exists():
        agent_logger.warning(f"工作流目录不存在: {workflows_dir}")
        return

    loaded = 0
    for workflow_dir in workflows_path.iterdir():
        if workflow_dir.is_dir() and workflow_dir.name != "__pycache__" and not workflow_dir.name.startswith("."):
            spec = load_workflow(str(workflow_dir))
            if spec:
                loaded += 1

    agent_logger.info(f"✅ 加载了 {loaded} 个工作流")

    # 刷新路由映射（支持热加载）
    try:
        from core.router import router
        router.refresh_route_map()
        agent_logger.info(f"✅ 路由映射已刷新（{len(router._route_map)} 条）")
    except Exception as e:
        agent_logger.warning(f"刷新路由映射失败: {e}")