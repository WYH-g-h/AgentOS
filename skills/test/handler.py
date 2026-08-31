# skills/test/handler.py
"""
测试技能：为代码生成单元测试
"""

from core.logger import agent_logger
from core.parser import parse_files, extract_filename
from core.health import health_check
from core.prompts import prompt_manager
from tools.registry import tool_registry
from models.manager import model_manager
from skills.registry import skill_registry


def handler(context) -> str:
    """测试技能实现"""
    agent_logger.info(f"执行测试技能: {context.user_input[:50]}...")

    skill_spec = skill_registry.get(context.current_skill)
    if skill_spec and skill_spec.model:
        model = model_manager.get_model_by_config(skill_spec.model)
        retries = skill_spec.retries
    else:
        model = model_manager.get_thinker()
        retries = 2

    if not model:
        return "❌ 模型未配置"

    # 提取目标文件
    target_file = extract_filename(context.user_input)
    if not target_file:
        return "❌ 请指定要生成测试的文件名，例如：测试 main.py"

    agent_logger.debug(f"目标文件: {target_file}")

    # 读取文件
    read_result = tool_registry.execute("read_file", filepath=target_file)
    if "❌" in read_result:
        return read_result

    content = read_result

    if not content or len(content.strip()) < 10:
        return f"❌ 文件 {target_file} 内容为空或太短"

    # 生成测试文件名
    base_name = target_file.rsplit('.', 1)[0] if '.' in target_file else target_file
    test_file = f"test_{base_name}.py"

    # 使用提示词管理器
    system_prompt, user_prompt = prompt_manager.get_formatted(
        "skill_test",
        target_file=target_file,
        content=content[:3000],
        user_input=context.user_input
    )

    if not user_prompt:
        user_prompt = f"""目标文件: {target_file}

代码:
{content[:3000]}

测试要求: {context.user_input}

请生成完整的单元测试代码，输出格式:
FILE: {test_file}
CONTENT:
[完整的测试代码]
ENDCONTENT"""

    messages = [
        {"role": "system", "content": system_prompt or "你是一个测试工程师"},
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
        return f"❌ 无法解析测试代码\n\n模型输出预览:\n{plan[:500]}"

    if test_file not in files:
        if files:
            test_file = list(files.keys())[0]
        else:
            return "❌ 没有找到测试文件内容"

    test_content = files[test_file]
    if not test_content or len(test_content.strip()) < 10:
        return "❌ 测试内容为空或太短"

    # 写入测试文件
    write_result = tool_registry.execute("write_file", filepath=test_file, content=test_content)
    if "❌" in write_result:
        return write_result

    # 验证测试文件
    verify_result = tool_registry.execute("verify_file", filepath=test_file)

    result_msg = f"✅ 已生成测试 {test_file}\n{write_result}"
    if "✅" in verify_result:
        result_msg += f"\n{verify_result}"
    else:
        result_msg += f"\n⚠️ {verify_result}"

    return result_msg