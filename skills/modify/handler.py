# skills/modify/handler.py
"""
修改技能：读取文件 → 修改内容 → 写入 → 验证
支持工作流模式
"""

import re
import time
from core.logger import agent_logger
from core.parser import parse_files, parse_modify, extract_filename
from core.health import health_check
from tools.registry import tool_registry
from models.manager import model_manager
from skills.registry import skill_registry


def _ensure_correct_format(text: str, target_file: str) -> str:
    """确保输出有正确的 FILE: 和 CONTENT: 格式"""
    if "FILE:" in text and "CONTENT:" in text:
        return text

    if text.startswith("```") and text.endswith("```"):
        lines = text.split("\n")
        if len(lines) > 2:
            content = "\n".join(lines[1:-1])
            return f"FILE: {target_file}\nCONTENT:\n{content}\nENDCONTENT"

    if len(text) > 100:
        return f"FILE: {target_file}\nCONTENT:\n{text}\nENDCONTENT"

    return text


def _extract_content_aggressive(text: str, target_file: str) -> dict:
    """激进的内容提取 - 尝试多种模式"""
    # 模式1: 标准 FILE: CONTENT: 格式
    files = parse_files(text)
    if files:
        return files

    # 模式2: MODIFY: 格式
    files = parse_modify(text)
    if files:
        return files

    # 模式3: 代码块提取
    code_block_match = re.search(r'```(?:\w+)?\s*([\s\S]*?)```', text)
    if code_block_match:
        content = code_block_match.group(1).strip()
        if content:
            return {target_file: content}

    # 模式4: JSON 直接提取
    if target_file.endswith('.json'):
        try:
            import json
            json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
            if json_match:
                content = json_match.group(1).strip()
                json.loads(content)
                if content and len(content) > 10:
                    return {target_file: content}
        except Exception:
            pass

    # 模式5: 寻找内容行
    lines = text.split('\n')
    content_lines = []
    start_collecting = False

    for line in lines:
        if re.match(r'^(?:FILE:|MODIFY:|CONTENT:|内容:|以下是修改后的|修改后的文件|完整内容)',
                    line, re.IGNORECASE):
            start_collecting = True
            continue

        if start_collecting and re.match(r'^(?:ENDCONTENT|```|---|===|【文件结束】)', line):
            break

        if start_collecting:
            if line.strip() and not re.match(r'^[\s]*$', line):
                content_lines.append(line)
        else:
            if line.strip() and len(line.strip()) > 10:
                content_lines.append(line)

    if content_lines:
        content = '\n'.join(content_lines).strip()
        if content and len(content) > 20:
            return {target_file: content}

    return {}


def handler(context) -> str:
    """修改技能实现 - 支持工作流模式"""
    agent_logger.info(f"执行修改技能: {context.user_input[:50]}...")

    skill_spec = skill_registry.get(context.current_skill)
    if skill_spec and skill_spec.model:
        model = model_manager.get_model_by_config(skill_spec.model)
        retries = skill_spec.retries
    else:
        model = model_manager.get_doer()
        retries = 2

    if not model:
        return "❌ 模型未配置"

    # ============================================================
    # 第一步：确定目标文件
    # ============================================================
    target_file = None

    output_filename = context.get_state("output")
    if output_filename:
        target_file = output_filename

    if not target_file:
        target_file = extract_filename(context.user_input)

    if not target_file:
        step_params = context.get_state("step_params", {})
        if step_params and step_params.get("output"):
            target_file = step_params.get("output")

    if not target_file:
        return "❌ 请指定要修改的文件名，例如：修改 a.html"

    agent_logger.debug(f"目标文件: {target_file}")

    # 读取文件
    read_result = tool_registry.execute("read_file", filepath=target_file)
    if "❌" in read_result:
        return read_result

    current_content = read_result

    if not current_content or len(current_content.strip()) < 10:
        return f"❌ 文件 {target_file} 内容为空或太短，无法修改"

    # 提取修改要求（去掉文件名和"修改"前缀）
    user_requirement = context.user_input
    user_requirement = re.sub(r'[a-zA-Z0-9_\-\.]+\.\w+', '', user_requirement)
    user_requirement = re.sub(r'^(修改|更新|调整|改成|换成|改动|编辑)\s*', '', user_requirement).strip()

    if not user_requirement:
        user_requirement = "请对文件内容进行合理优化"

    # 检测文件类型
    file_ext = target_file.split('.')[-1] if '.' in target_file else 'txt'
    file_type_map = {
        'json': 'JSON 数据',
        'py': 'Python 代码',
        'html': 'HTML 代码',
        'js': 'JavaScript 代码',
        'css': 'CSS 代码',
        'md': 'Markdown 文档',
        'txt': '文本文件',
        'yaml': 'YAML 配置',
        'yml': 'YAML 配置',
    }
    file_type = file_type_map.get(file_ext, '文本文件')

    # 生成修改方案
    prompt = f"""你是一个文件修改助手。请修改以下 {file_type} 文件。

【当前文件内容】
{current_content[:3000]}

【文件类型】：{file_type}
【修改要求】：{user_requirement}

【重要：输出格式要求】
你必须严格按照以下格式输出，不要添加任何额外说明、思考过程或解释：

FILE: {target_file}
CONTENT:
[完整的修改后代码]
ENDCONTENT

注意：
1. 必须输出完整的文件内容，不要只输出修改的部分
2. 代码块不要用```包裹
3. 直接输出 FILE: 开始的内容
4. 保持原有文件格式和结构
5. 如果文件是 JSON，确保修改后仍是有效的 JSON 格式
6. 如果修改要求不明确，请做出合理的改进

请直接输出修改后的完整文件内容。"""

    agent_logger.debug(f"修改要求: {user_requirement}")

    result, error = health_check.safe_call(
        model.invoke, prompt, max_retries=retries
    )

    if error:
        return error

    plan = result.content if result else ""

    agent_logger.debug(f"LLM 输出长度: {len(plan)}")

    # 如果 LLM 输出为空，尝试降级方案
    if not plan or len(plan.strip()) < 10:
        agent_logger.warning("LLM 输出为空，使用降级方案")
        # 在文件末尾添加修改时间戳
        import time
        simple_content = current_content + f"\n# Modified at {time.strftime('%Y-%m-%d %H:%M:%S')}"
        write_result = tool_registry.execute("write_file", filepath=target_file, content=simple_content)
        return f"⚠️ LLM 未生成修改方案，已添加时间戳标记\n{write_result}"

    # 尝试修复格式
    plan = _ensure_correct_format(plan, target_file)

    # 解析修改后的内容
    files = _extract_content_aggressive(plan, target_file)

    if not files:
        # 最后一次尝试：直接用正则提取
        content_match = re.search(r'CONTENT:\s*([\s\S]*?)(?:ENDCONTENT|$)', plan, re.IGNORECASE)
        if content_match:
            content = content_match.group(1).strip()
            if content and len(content) > 20:
                files = {target_file: content}

    if not files:
        # 尝试把整个输出当作内容
        if len(plan.strip()) > 50:
            files = {target_file: plan.strip()}

    if not files:
        return f"❌ 无法解析修改后的内容\n\n模型输出预览:\n{plan[:800]}"

    if target_file not in files:
        if files:
            target_file = list(files.keys())[0]
        else:
            return "❌ 没有找到修改后的文件内容"

    new_content = files[target_file]
    if not new_content or len(new_content.strip()) < 10:
        return "❌ 修改后的内容为空或太短"

    # 写入文件
    write_result = tool_registry.execute("write_file", filepath=target_file, content=new_content)
    if "❌" in write_result:
        return write_result

    # 验证文件
    verify_result = tool_registry.execute("verify_file", filepath=target_file)

    if "✅" in verify_result:
        return f"✅ 已修改 {target_file}\n{verify_result}"
    else:
        return f"⚠️ 已修改但验证失败: {verify_result}\n{write_result}"