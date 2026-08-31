# skills/refactor/handler.py
"""
重构技能：重构代码，优化结构和可读性
支持工作流模式
"""

from core.logger import agent_logger
from core.parser import parse_files, extract_filename
from core.health import health_check
from core.prompts import prompt_manager
from tools.registry import tool_registry
from models.manager import model_manager
from skills.registry import skill_registry


def handler(context) -> str:
    """重构技能实现 - 支持工作流模式"""
    agent_logger.info(f"执行重构技能: {context.user_input[:50]}...")

    skill_spec = skill_registry.get(context.current_skill)
    if skill_spec and skill_spec.model:
        model = model_manager.get_model_by_config(skill_spec.model)
        retries = skill_spec.retries
    else:
        model = model_manager.get_thinker()
        retries = 2

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
        agent_logger.debug(f"工作流指定重构文件: {target_file}")

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
        return "❌ 请指定要重构的文件名，例如：重构 main.py"

    agent_logger.debug(f"目标文件: {target_file}")

    # 读取文件
    read_result = tool_registry.execute("read_file", filepath=target_file)
    if "❌" in read_result:
        return read_result

    content = read_result

    if not content or len(content.strip()) < 10:
        return f"❌ 文件 {target_file} 内容为空或太短，无法重构"

    # 使用提示词管理器
    system_prompt, user_prompt = prompt_manager.get_formatted(
        "skill_refactor",
        target_file=target_file,
        content=content[:4000],
        user_input=context.user_input
    )

    if not user_prompt:
        user_prompt = f"""文件: {target_file}

当前代码:
{content[:4000]}

重构要求: {context.user_input}

输出格式:
FILE: {target_file}
CONTENT:
[完整的重构后代码]
ENDCONTENT"""

    messages = [
        {"role": "system", "content": system_prompt or "你是一个代码重构专家"},
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
        return f"❌ 无法解析重构后的内容\n\n模型输出预览:\n{plan[:500]}"

    if target_file not in files:
        if files:
            target_file = list(files.keys())[0]
        else:
            return "❌ 没有找到重构后的文件内容"

    new_content = files[target_file]
    if not new_content or len(new_content.strip()) < 10:
        return "❌ 重构后的内容为空或太短"

    # 写入文件
    write_result = tool_registry.execute("write_file", filepath=target_file, content=new_content)
    if "❌" in write_result:
        return write_result

    # 验证文件
    verify_result = tool_registry.execute("verify_file", filepath=target_file)

    result_msg = f"✅ 已重构 {target_file}\n{write_result}"
    if "✅" in verify_result:
        result_msg += f"\n{verify_result}"
    else:
        result_msg += f"\n⚠️ {verify_result}"

    return result_msg