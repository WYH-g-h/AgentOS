# skills/analyze/handler.py
"""
分析技能：读取文件 → 分析内容 → 总结输出
使用技能配置中的模型
"""

import re
from core.logger import agent_logger
from core.parser import extract_filename
from core.health import health_check
from core.prompts import prompt_manager
from tools.registry import tool_registry
from models.manager import model_manager
from skills.registry import skill_registry


def handler(context) -> str:
    """分析技能实现"""
    agent_logger.info(f"执行分析技能: {context.user_input[:50]}...")

    skill_spec = skill_registry.get(context.current_skill)
    if skill_spec and skill_spec.model:
        # ✅ 分析任务使用 thinker 模型更好
        model = model_manager.get_model_by_config(skill_spec.model)
        retries = skill_spec.retries
    else:
        model = model_manager.get_thinker()  # ✅ 改为 thinker
        retries = 2

    if not model:
        return "❌ 模型未配置"

    # ✅ 一次性提取文件名
    target_file = extract_filename(context.user_input)

    # ============================================================
    # 纯文本分析模式（用于工作流）
    # ============================================================
    if not target_file:
        # ✅ 检查工作流参数
        output_file = context.get_state("output")

        system_prompt, user_prompt = prompt_manager.get_formatted(
            "skill_analyze",
            target_file=output_file or "需求分析",
            content="",
            user_input=context.user_input
        )

        if not user_prompt:
            user_prompt = f"""
请分析以下用户需求，提取关键信息：

【用户输入】：
{context.user_input}

【输出要求】：
1. 核心功能：用户想要什么功能
2. 技术要点：需要用到的技术
3. 实现步骤：分步骤说明
4. 预期输出：应该生成什么

用简洁、清晰的结构输出。
"""

        messages = [
            {"role": "system", "content": system_prompt or "你是一个需求分析专家"},
            {"role": "user", "content": user_prompt}
        ]

        result, error = health_check.safe_call(
            model.invoke, messages, max_retries=retries
        )

        if error:
            return error

        analysis = result.content if result else ""

        # ✅ 如果工作流指定了输出文件，保存结果
        if output_file:
            write_result = tool_registry.execute("write_file", filepath=output_file, content=analysis)
            return f"📊 需求分析已保存到 {output_file}\n\n{analysis}\n\n{write_result}"

        return f"📊 需求分析:\n\n{analysis}"

    # ============================================================
    # 文件分析模式
    # ============================================================
    agent_logger.debug(f"目标文件: {target_file}")

    read_result = tool_registry.execute("read_file", filepath=target_file)
    if "❌" in read_result:
        return read_result

    content = read_result

    # ✅ 检查工作流输出参数
    output_file = context.get_state("output")

    system_prompt, user_prompt = prompt_manager.get_formatted(
        "skill_analyze",
        target_file=target_file,
        content=content[:3000],
        user_input=context.user_input
    )

    if not user_prompt:
        user_prompt = f"""
请分析以下文件 {target_file} 的内容：
{content[:3000]}

请回答：
1. 这个文件是做什么的？
2. 它包含哪些主要结构或功能？
3. 有什么问题或改进建议吗？

用户要求：{context.user_input}
"""

    messages = [
        {"role": "system", "content": system_prompt or "你是一个代码分析专家"},
        {"role": "user", "content": user_prompt}
    ]

    agent_logger.debug("生成分析...")

    result, error = health_check.safe_call(
        model.invoke, messages, max_retries=retries
    )

    if error:
        return error

    analysis = result.content if result else ""

    # ✅ 如果工作流指定了输出文件，保存结果
    if output_file:
        write_result = tool_registry.execute("write_file", filepath=output_file, content=analysis)
        return f"📊 分析 {target_file} 已保存到 {output_file}\n\n{analysis}\n\n{write_result}"

    return f"📊 分析 {target_file}:\n\n{analysis}"