# skills/summarize/handler.py
"""
总结技能：总结文件或文档内容
"""

import re
from core.logger import agent_logger
from core.parser import extract_filename
from core.health import health_check
from tools.registry import tool_registry
from models.manager import model_manager
from skills.registry import skill_registry


def handler(context) -> str:
    """总结技能实现"""
    agent_logger.info(f"执行总结技能: {context.user_input[:50]}...")

    # 读取技能配置
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
        agent_logger.debug(f"工作流指定总结文件: {target_file}")

    # 2. 从用户输入中提取文件名
    if not target_file:
        target_file = extract_filename(context.user_input)

    # 3. 如果还是没有，尝试从 step_params 获取
    if not target_file:
        step_params = context.get_state("step_params", {})
        if step_params and step_params.get("output"):
            target_file = step_params.get("output")
            agent_logger.debug(f"从 step_params 获取: {target_file}")

    if not target_file:
        return "❌ 请指定要总结的文件名，例如：总结 test.txt"

    agent_logger.debug(f"目标文件: {target_file}")

    # ============================================================
    # 第二步：读取文件
    # ============================================================
    read_result = tool_registry.execute("read_file", filepath=target_file)
    if "❌" in read_result:
        return read_result

    content = read_result

    # 检查内容长度
    if len(content) < 50:
        return f"📄 {target_file} 内容太短，不需要总结:\n\n{content}"

    # ============================================================
    # 第三步：提取总结要求
    # ============================================================
    requirements = context.user_input
    # 移除文件名
    requirements = re.sub(r'[a-zA-Z0-9_\-\.]+\.\w+', '', requirements)
    # 移除 "总结" 前缀
    requirements = re.sub(r'^(总结|概括|汇总|提炼|摘要)\s*', '', requirements).strip()

    if not requirements:
        requirements = "请给出一个简洁、全面的总结"

    # ============================================================
    # 第四步：使用 LLM 生成总结
    # ============================================================
    content_preview = content[:4000]
    if len(content) > 4000:
        content_preview += "\n\n... (内容已截断，共 " + str(len(content)) + " 字符)"

    # 如果是在工作流中，调整提示词
    if context.current_workflow:
        prompt = f"""请总结以下文件 {target_file} 的内容。

【文件内容】：
{content_preview}

【总结要求】：
这是一个工作流步骤 ({context.current_workflow})，请生成结构化的总结。

【格式要求】：
1. 用结构化的方式总结（分点或分段落）
2. 提取核心要点和关键信息
3. 如果文件是代码，总结功能和技术要点
4. 如果文件是文档，总结主要内容和结论
5. 语言简洁、清晰

【总结】："""
    else:
        prompt = f"""请总结以下文件 {target_file} 的内容。

            【文件内容】：
            {content_preview}
            
            【总结要求】：
            {requirements}
            
            【格式要求】：
            1. 用结构化的方式总结（分点或分段落）
            2. 提取核心要点和关键信息
            3. 如果文件是代码，总结功能和技术要点
            4. 如果文件是文档，总结主要内容和结论
            5. 语言简洁、清晰
            
            【总结】："""

    agent_logger.debug("生成总结...")

    result, error = health_check.safe_call(
        model.invoke, prompt, max_retries=retries
    )

    if error:
        return error

    summary = result.content if result else ""

    if not summary or len(summary) < 10:
        return f"⚠️ 无法生成总结\n\n原始内容:\n{content[:500]}..."

    return f"📊 总结 {target_file}:\n\n{summary}"