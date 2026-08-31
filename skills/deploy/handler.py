# skills/deploy/handler.py
"""
部署技能：部署项目到目标环境
"""

import os
from core.logger import agent_logger
from core.health import health_check
from core.prompts import prompt_manager
from core.config import config
from tools.registry import tool_registry
from models.manager import model_manager
from skills.registry import skill_registry


def handler(context) -> str:
    """部署技能实现"""
    agent_logger.info(f"执行部署技能: {context.user_input[:50]}...")

    skill_spec = skill_registry.get(context.current_skill)
    if skill_spec and skill_spec.model:
        model = model_manager.get_model_by_config(skill_spec.model)
        retries = skill_spec.retries
    else:
        model = model_manager.get_doer()
        retries = 2

    if not model:
        return "❌ 模型未配置"

    # 获取输出目录
    output_dir = config.get("paths.output", "./output")

    # 检测项目类型
    project_type = detect_project_type(output_dir)
    project_name = os.path.basename(output_dir)

    agent_logger.debug(f"项目类型: {project_type}, 项目名: {project_name}")

    # 生成部署方案
    system_prompt, user_prompt = prompt_manager.get_formatted(
        "skill_deploy",
        project_name=project_name,
        project_type=project_type,
        target=context.user_input,
        user_input=context.user_input
    )

    if not user_prompt:
        user_prompt = f"""项目: {project_name}
项目类型: {project_type}
输出目录: {output_dir}

部署要求: {context.user_input}

请生成完整的部署方案，包括:
1. 环境检查
2. 依赖安装
3. 构建命令
4. 启动命令
5. 验证步骤

输出格式: 分步骤说明，包含具体命令。"""

    messages = [
        {"role": "system", "content": system_prompt or "你是一个部署工程师"},
        {"role": "user", "content": user_prompt}
    ]

    result, error = health_check.safe_call(
        model.invoke, messages, max_retries=retries
    )

    if error:
        return error

    plan = result.content if result else ""

    if not plan or len(plan.strip()) < 20:
        return "❌ 生成的部署方案为空"

    # 尝试执行部署命令
    results = []
    lines = plan.split('\n')
    for line in lines:
        if line.strip().startswith(('npm ', 'pip ', 'python ', 'git ', 'docker')):
            cmd = line.strip()
            agent_logger.info(f"执行部署命令: {cmd[:50]}...")
            cmd_result = tool_registry.execute("run_command", command=cmd)
            results.append(f"  {cmd_result}")

    result_msg = f"📦 部署方案:\n\n{plan}\n"
    if results:
        result_msg += "\n" + "\n".join(results)

    return result_msg


def detect_project_type(directory: str) -> str:
    """检测项目类型"""
    # 检查文件特征
    files = []
    if os.path.exists(directory):
        try:
            files = os.listdir(directory)
        except Exception:
            pass

    files_lower = [f.lower() for f in files]

    if 'package.json' in files_lower:
        return 'nodejs'
    elif 'requirements.txt' in files_lower or any(f.endswith('.py') for f in files):
        return 'python'
    elif 'pom.xml' in files_lower or 'build.gradle' in files_lower:
        return 'java'
    elif 'go.mod' in files_lower:
        return 'golang'
    elif 'Cargo.toml' in files_lower:
        return 'rust'
    elif 'Dockerfile' in files_lower:
        return 'docker'
    else:
        return 'general'