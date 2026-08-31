# skills/create/handler.py
"""
创建技能：生成文件内容 → 写入 → 验证
使用技能配置中的模型
支持多行内容输入
智能判断直接写入 vs LLM生成
"""

import re
from datetime import datetime
from core.logger import agent_logger
from core.parser import parse_files, extract_filename
from core.health import health_check
from tools.registry import tool_registry
from models.manager import model_manager
from skills.registry import skill_registry


def _is_likely_code(content: str) -> bool:
    """判断内容是否像代码"""
    code_patterns = [
        r'def\s+\w+\s*\(', r'class\s+\w+', r'import\s+\w+', r'from\s+\w+\s+import',
        r'function\s+\w+\s*\(', r'var\s+\w+\s*=', r'const\s+\w+\s*=', r'let\s+\w+\s*=',
        r'<html', r'<div', r'<body', r'{"', r'\[', r'```',
        r'print\s*\(', r'return\s+', r'if\s+.*:', r'for\s+.*:',
    ]
    return any(re.search(p, content, re.IGNORECASE) for p in code_patterns)


def _is_likely_requirement(content: str) -> bool:
    """判断内容是否像需求描述"""
    req_patterns = [
        r'实现', r'生成', r'写一个', r'做一个', r'创建', r'帮我', r'请',
        r'功能', r'系统', r'工具', r'脚本', r'程序', r'软件',
    ]
    return any(kw in content for kw in req_patterns)


def handler(context) -> str:
    """创建技能实现 - 支持多行内容"""
    agent_logger.info(f"执行创建技能: {context.user_input[:50]}...")

    # 读取技能配置
    skill_spec = skill_registry.get(context.current_skill)
    if skill_spec and skill_spec.model:
        model = model_manager.get_model_by_config(skill_spec.model)
        timeout = skill_spec.timeout
        retries = skill_spec.retries
    else:
        model = model_manager.get_thinker()
        timeout = 90
        retries = 2

    if not model:
        return "❌ 模型未配置"

    # ============================================================
    # 第一步：确定目标文件
    # ============================================================
    target_file = None

    # 1. 从 params 中获取（工作流模式）
    output_filename = context.get_state("output")
    if output_filename:
        target_file = output_filename
        agent_logger.debug(f"工作流指定输出: {target_file}")

    # 2. 从用户输入中提取
    if not target_file:
        target_file = extract_filename(context.user_input)

    # 3. 从 step_params 获取
    if not target_file:
        step_params = context.get_state("step_params", {})
        if step_params and step_params.get("output"):
            target_file = step_params.get("output")
            agent_logger.debug(f"从 step_params 获取: {target_file}")

    # 4. 工作流模式生成默认文件名
    if not target_file and context.current_workflow:
        target_file = f"{context.current_workflow}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        agent_logger.debug(f"生成默认文件名: {target_file}")

    if not target_file:
        return "❌ 请指定要创建的文件名，例如：创建 a.html"

    agent_logger.debug(f"目标文件: {target_file}")

    # ============================================================
    # 第二步：智能判断是否直接写入
    # ============================================================

    user_input = context.user_input

    # 提取 "内容为" / "内容是" / "内容：" 后面的内容
    content_match = re.search(r'内容\s*[是为：:]\s*(.+)', user_input)

    if content_match:
        user_provided_content = content_match.group(1).strip()

        if user_provided_content and len(user_provided_content) > 0:
            agent_logger.debug(f"从 '内容为' 提取: {user_provided_content[:50]}...")

            # ✅ 判断是"具体内容"还是"需求描述"
            is_code = _is_likely_code(user_provided_content)
            is_requirement = _is_likely_requirement(user_provided_content)

            # 如果内容有代码特征 或 长度超过100字符 或 不是需求描述，直接写入
            if is_code or len(user_provided_content) > 100 or not is_requirement:
                agent_logger.info("检测到具体内容，直接写入")
                write_result = tool_registry.execute("write_file", filepath=target_file, content=user_provided_content)
                if "❌" in write_result:
                    return write_result
                verify_result = tool_registry.execute("verify_file", filepath=target_file)
                result_msg = f"✅ 已创建 {target_file}\n{write_result}"
                if "✅" in verify_result:
                    result_msg += f"\n{verify_result}"
                else:
                    result_msg += f"\n⚠️ {verify_result}"
                return result_msg
            else:
                # 是需求描述，走 LLM 生成
                user_requirement = user_provided_content
                agent_logger.info("检测到需求描述，使用 LLM 生成内容")
        else:
            user_requirement = "创建一个文件"
    else:
        # 没有 "内容为"，提取需求
        user_requirement = user_input
        # 移除路由符号
        user_requirement = re.sub(r'^[\[【(（]\s*', '', user_requirement)
        user_requirement = re.sub(r'[\】】)）]\s*', '', user_requirement)
        # 移除 "创建 xxx" 前缀
        user_requirement = re.sub(r'^(创建|新建|生成|写一个|做一个|实现)\s+[a-zA-Z0-9_\-\.]+\.\w+\s*', '', user_requirement)
        user_requirement = user_requirement.strip()

    # 如果用户要求为空，用默认描述
    if not user_requirement:
        user_requirement = f"创建一个 {target_file} 文件"

    # ============================================================
    # 第三步：使用 LLM 生成内容
    # ============================================================

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
        'csv': 'CSV 数据',
        'yaml': 'YAML 配置',
        'yml': 'YAML 配置',
    }
    file_type = file_type_map.get(file_ext, '文本文件')

    # ============================================================
    # 如果是 HTML 文件，添加完整结构要求
    # ============================================================
    html_template_hint = ""
    if target_file.endswith('.html'):
        html_template_hint = """
【HTML 结构要求】：
必须生成完整的 HTML 页面，包含以下所有标签：
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>页面标题</title>
</head>
<body>
    <!-- 页面内容 -->
</body>
</html>"""

    if context.current_workflow:
        step_name = context.current_step or "generate"
        prompt = f"""你是一个代码生成助手。请根据用户需求生成 {target_file} 的内容。

【用户需求】：
{user_requirement}
{html_template_hint}

【当前步骤】：{step_name}
【文件类型】：{file_type}
【输出文件】：{target_file}

【重要：输出格式要求】
你必须严格按照以下格式输出，不要添加任何额外说明：

FILE: {target_file}
CONTENT:
[完整的 {file_type} 内容]
ENDCONTENT

注意：
1. 必须输出完整的文件内容
2. 如果是代码，确保语法正确
3. 如果是文档，确保结构清晰
4. 不要用 ``` 包裹代码块
5. 如果是 HTML，必须包含完整结构（DOCTYPE, html, head, body）"""
    else:
        prompt = f"""你是一个代码生成助手。请根据用户需求生成文件内容。

用户要求：{user_requirement}
{html_template_hint}

请创建文件 {target_file}，输出完整内容：
FILE: {target_file}
CONTENT:
[完整的文件内容]
ENDCONTENT

注意：
1. 必须输出完整的文件内容
2. 如果是代码，确保语法正确
3. 如果是文档，确保结构清晰
4. 不要用 ``` 包裹代码块
5. 如果用户指定了内容类型，按用户要求生成
6. 如果是 HTML，必须包含完整结构（DOCTYPE, html, head, body）"""

    agent_logger.debug("生成文件内容...")

    result, error = health_check.safe_call(
        model.invoke, prompt, max_retries=retries
    )

    if error:
        return error

    plan = result.content if result else ""

    # ============================================================
    # 第四步：解析内容
    # ============================================================
    files = parse_files(plan)

    if not files:
        content_match = re.search(r'CONTENT:\s*(.*?)(?:ENDCONTENT|$)', plan, re.DOTALL | re.IGNORECASE)
        if content_match:
            content = content_match.group(1).strip()
            if content and len(content) > 10:
                files = {target_file: content}
                agent_logger.debug("使用宽松解析提取内容")

    if not files:
        code_match = re.search(r'```(?:\w+)?\s*([\s\S]*?)```', plan)
        if code_match:
            content = code_match.group(1).strip()
            if content and len(content) > 10:
                files = {target_file: content}
                agent_logger.debug("从代码块提取内容")

    if not files:
        agent_logger.debug(f"解析失败，LLM 输出预览: {plan[:500]}")
        return "❌ 无法解析生成的内容"

    if target_file not in files:
        if files:
            target_file = list(files.keys())[0]
        else:
            return "❌ 没有找到文件内容"

    content = files[target_file]
    if not content or len(content.strip()) < 5:
        return "❌ 生成的内容为空或太短"

    # ============================================================
    # 第五步：如果是 HTML，验证并补全结构
    # ============================================================
    if target_file.endswith('.html'):
        content_lower = content.lower()
        if '<!DOCTYPE html' not in content_lower and '<html' not in content_lower:
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            title = title_match.group(1) if title_match else target_file.replace('.html', '')

            body_match = re.search(r'<body>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
            body_content = body_match.group(1).strip() if body_match else content

            content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        h1 {{ color: #333; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
    </style>
</head>
<body>
    <div class="container">
        {body_content if body_content else content}
    </div>
</body>
</html>"""
            agent_logger.debug("已补全 HTML 结构")

    # ============================================================
    # 第六步：写入和验证
    # ============================================================
    write_result = tool_registry.execute("write_file", filepath=target_file, content=content)
    if "❌" in write_result:
        return write_result

    verify_result = tool_registry.execute("verify_file", filepath=target_file)

    result_msg = f"✅ 已创建 {target_file}\n{write_result}"
    if "✅" in verify_result:
        result_msg += f"\n{verify_result}"
    else:
        result_msg += f"\n⚠️ {verify_result}"

    return result_msg