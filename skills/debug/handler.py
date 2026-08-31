# skills/debug/handler.py
"""
调试技能：分析和修复代码错误
支持工作流模式
"""

import re
from core.logger import agent_logger
from core.parser import parse_files, extract_filename
from core.health import health_check
from core.prompts import prompt_manager
from tools.registry import tool_registry
from models.manager import model_manager
from skills.registry import skill_registry


def handler(context) -> str:
    """调试技能实现 - 支持工作流模式"""
    agent_logger.info(f"执行调试技能: {context.user_input[:50]}...")

    skill_spec = skill_registry.get(context.current_skill)
    if skill_spec and skill_spec.model:
        model = model_manager.get_model_by_config(skill_spec.model)
        retries = skill_spec.retries
    else:
        model = model_manager.get_doer()
        retries = 3

    if not model:
        return "❌ 模型未配置"

    # ============================================================
    # 第一步：确定目标文件（支持工作流模式）
    # ============================================================
    target_file = None

    # 1. 从 params 中获取（工作流模式）
    output_filename = context.get_state("output")
    if output_filename:
        target_file = output_filename
        agent_logger.debug(f"工作流指定调试文件: {target_file}")

    # 2. 从用户输入中提取
    if not target_file:
        target_file = extract_filename(context.user_input)

    # 3. 从 step_params 获取
    if not target_file:
        step_params = context.get_state("step_params", {})
        if step_params and step_params.get("output"):
            target_file = step_params.get("output")
            agent_logger.debug(f"从 step_params 获取: {target_file}")

    if not target_file:
        return "❌ 请指定要调试的文件名，例如：调试 main.py"

    agent_logger.debug(f"目标文件: {target_file}")

    # 读取文件
    read_result = tool_registry.execute("read_file", filepath=target_file)
    if "❌" in read_result:
        return read_result

    content = read_result

    if not content or len(content.strip()) < 10:
        return f"❌ 文件 {target_file} 内容为空或太短"

    # 提取错误信息
    error_info = ""
    error_match = re.search(r'错误[：:]\s*(.+?)(?:\n|$)', context.user_input)
    if error_match:
        error_info = error_match.group(1)

    # 如果用户提供了错误输出，尝试运行命令获取
    if not error_info and "运行" in context.user_input:
        # 尝试运行文件
        file_ext = target_file.split('.')[-1] if '.' in target_file else ''
        if file_ext == 'py':
            cmd_result = tool_registry.execute("run_command", command=f"python {target_file}")
            if "❌" in cmd_result:
                error_info = cmd_result

    # 使用提示词管理器
    system_prompt, user_prompt = prompt_manager.get_formatted(
        "skill_debug",
        target_file=target_file,
        content=content[:3000],
        error_info=error_info or "未提供具体错误信息",
        user_input=context.user_input
    )

    if not user_prompt:
        user_prompt = f"""文件: {target_file}

代码:
{content[:3000]}

错误信息: {error_info or '请分析代码中的潜在问题'}

用户描述: {context.user_input}

请分析问题并提供修复后的完整代码。"""

    messages = [
        {"role": "system", "content": system_prompt or "你是一个代码调试专家"},
        {"role": "user", "content": user_prompt}
    ]

    result, error = health_check.safe_call(
        model.invoke, messages, max_retries=retries
    )

    if error:
        return error

    plan = result.content if result else ""

    # 解析内容
    files = parse_files(plan)

    if not files:
        return f"❌ 无法解析调试后的内容\n\n模型输出预览:\n{plan[:500]}"

    if target_file not in files:
        if files:
            target_file = list(files.keys())[0]
        else:
            return "❌ 没有找到修复后的文件内容"

    new_content = files[target_file]
    if not new_content or len(new_content.strip()) < 10:
        return "❌ 修复后的内容为空或太短"

    # 写入文件
    write_result = tool_registry.execute("write_file", filepath=target_file, content=new_content)
    if "❌" in write_result:
        return write_result

    # 验证文件
    verify_result = tool_registry.execute("verify_file", filepath=target_file)

    result_msg = f"✅ 已调试修复 {target_file}\n{write_result}"
    if "✅" in verify_result:
        result_msg += f"\n{verify_result}"
    else:
        result_msg += f"\n⚠️ {verify_result}"

    return result_msg