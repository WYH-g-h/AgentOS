# core/prompts.py
"""
统一提示词管理 - 仅保留技能所需的提示词模板
"""

from typing import Dict, Optional
from dataclasses import dataclass

from core.logger import agent_logger


@dataclass
class PromptTemplate:
    """提示词模板"""
    system: str
    user: str
    version: str = "1.0"
    description: str = ""


class PromptManager:
    """提示词管理器 - 单例"""

    _instance = None
    _prompts: Dict[str, PromptTemplate] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_defaults()
        return cls._instance

    def _load_defaults(self):
        """加载默认提示词 - 仅保留技能需要的"""

        # ============================================================
        # 1. 分析技能 (analyze)
        # ============================================================
        self.register("skill_analyze", PromptTemplate(
            system="""你是一个代码分析专家。分析文件内容，提取关键信息。

分析维度:
1. 核心功能：这个文件是做什么的？
2. 主要结构：包含哪些主要组件或函数？
3. 技术要点：使用了哪些技术或框架？
4. 改进建议：有什么可以优化的地方？

输出要求: 结构化、清晰、简洁""",
            user="文件: {target_file}\n\n内容:\n{content}\n\n用户要求: {user_input}",
            description="分析文件"
        ))

        # ============================================================
        # 2. 调试技能 (debug)
        # ============================================================
        self.register("skill_debug", PromptTemplate(
            system="""你是一个代码调试专家。分析代码中的问题并提供修复方案。

调试步骤:
1. 分析错误信息（如果有）
2. 定位问题代码位置
3. 分析根本原因
4. 提供修复方案
5. 输出修复后的完整代码

输出格式:
【问题分析】...
【根本原因】...
【修复方案】...
【修复后的代码】
FILE: {target_file}
CONTENT:
[修复后的完整代码]
ENDCONTENT""",
            user="文件: {target_file}\n\n代码:\n{content}\n\n错误信息: {error_info}\n\n用户描述: {user_input}",
            description="代码调试"
        ))

        # ============================================================
        # 3. 部署技能 (deploy)
        # ============================================================
        self.register("skill_deploy", PromptTemplate(
            system="""你是一个部署工程师。根据项目类型生成可执行的部署方案。

部署步骤:
1. 环境检查
2. 依赖安装
3. 构建/编译
4. 配置设置
5. 启动服务

输出格式: 分步骤说明，每步包含具体命令。""",
            user="项目: {project_name}\n\n项目类型: {project_type}\n\n输出目录: {output_dir}\n\n部署要求: {user_input}",
            description="项目部署"
        ))

        # ============================================================
        # 4. 重构技能 (refactor)
        # ============================================================
        self.register("skill_refactor", PromptTemplate(
            system="""你是一个代码重构专家。在保持功能不变的前提下优化代码结构。

重构原则:
1. 保持功能完全一致
2. 提高代码可读性
3. 遵循最佳实践
4. 添加必要的注释
5. 保持原有代码风格

输出完整的重构后代码。""",
            user="文件: {target_file}\n\n当前代码:\n{content}\n\n重构要求: {user_input}",
            description="代码重构"
        ))

        # ============================================================
        # 5. 测试技能 (test)
        # ============================================================
        self.register("skill_test", PromptTemplate(
            system="""你是一个测试工程师。为目标代码生成单元测试。

测试要求:
1. 覆盖主要功能函数
2. 包含正常路径和边界条件
3. 使用适当的测试框架
4. 测试用例清晰、可执行

输出完整的测试代码。""",
            user="目标文件: {target_file}\n\n代码:\n{content}\n\n测试要求: {user_input}",
            description="生成测试"
        ))

        # ============================================================
        # 6. 代码审查 (code_review) - 被 analyze 技能使用
        # ============================================================
        self.register("code_review", PromptTemplate(
            system="""你是一个代码审查专家。审查代码质量，只输出发现的问题。

检查维度:
1. 代码规范
2. 潜在Bug
3. 性能问题
4. 安全漏洞
5. 可维护性

输出格式: 每行一个问题，不要给出修改建议。
如果没有问题，输出"通过"。""",
            user="文件: {target_file}\n\n代码:\n{content}",
            description="代码审查"
        ))

        # ============================================================
        # 7. 总结技能 (summarize) - 被技能使用
        # ============================================================
        self.register("skill_summarize", PromptTemplate(
            system="""你是一个文档总结助手。请用结构化方式总结文件内容。

要求:
1. 提取核心要点 (3-5个)
2. 分点或分段落呈现
3. 语言简洁、清晰
4. 总字数控制在500字以内""",
            user="文件: {target_file}\n\n内容:\n{content}\n\n总结要求: {requirements}",
            description="总结文档"
        ))

        # ============================================================
        # 8. 修改技能 (modify) - 被技能使用
        # ============================================================
        self.register("skill_modify", PromptTemplate(
            system="""你是一个文件修改助手。根据用户要求修改文件内容。

输出格式:
FILE: {target_file}
CONTENT:
[完整的修改后代码]
ENDCONTENT

注意:
1. 必须输出完整的文件内容
2. 保持原有代码风格
3. 确保修改后的代码语法正确""",
            user="文件: {target_file}\n\n当前内容:\n{current_content}\n\n修改要求: {user_input}",
            description="修改文件"
        ))

        # ============================================================
        # 9. 创建技能 (create) - 被技能使用
        # ============================================================
        self.register("skill_create", PromptTemplate(
            system="""你是一个代码生成助手。根据用户需求生成文件内容。

输出格式:
FILE: 文件名
CONTENT:
[完整的文件内容]
ENDCONTENT

注意:
1. 必须输出完整的文件内容
2. 如果是代码，确保语法正确
3. 如果是文档，确保结构清晰
4. 不要用 ``` 包裹代码块""",
            user="用户要求：{user_input}\n\n目标文件：{target_file}\n\n工作流上下文：{workflow_context}",
            description="创建文件"
        ))

        # ============================================================
        # 10. 搜索技能 (search) - 被技能使用
        # ============================================================
        self.register("skill_search", PromptTemplate(
            system="""你是一个搜索助手。根据搜索结果总结信息。

请总结:
1. 找到了哪些相关内容
2. 每个内容的要点是什么
3. 整体结论""",
            user="搜索关键词: {keyword}\n\n搜索范围: {search_dir}",
            description="搜索内容"
        ))

    def register(self, name: str, template: PromptTemplate):
        """注册提示词模板"""
        self._prompts[name] = template

    def get(self, name: str) -> Optional[PromptTemplate]:
        """获取提示词模板"""
        return self._prompts.get(name)

    def get_formatted(self, name: str, **kwargs) -> tuple:
        """获取格式化后的提示词"""
        template = self.get(name)
        if not template:
            return None, None

        try:
            # 为所有模板提供默认值
            if name.startswith("skill_"):
                kwargs.setdefault("user_input", "")
                kwargs.setdefault("target_file", "未指定文件")
                kwargs.setdefault("content", "")
                kwargs.setdefault("requirements", "无特殊要求")

            system = template.system.format(**kwargs) if kwargs else template.system
            user = template.user.format(**kwargs) if kwargs else template.user
            return system, user
        except KeyError as e:
            agent_logger.warning(f"提示词格式化失败 {name}: 缺少参数 {e}")
            return template.system, template.user

    def list_all(self) -> Dict[str, str]:
        """列出所有提示词"""
        return {name: t.description for name, t in self._prompts.items()}


# 全局提示词管理器
prompt_manager = PromptManager()