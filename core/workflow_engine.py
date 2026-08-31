# core/workflow_engine.py
"""
工作流执行引擎：支持依赖图、条件执行、参数传递
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass

from .context import ExecutionContext
from .logger import agent_logger
from skills.registry import skill_registry


@dataclass
class WorkflowStepResult:
    """工作流步骤结果"""
    step_name: str
    success: bool
    result: str
    error: Optional[str] = None
    outputs: Dict[str, Any] = None


class WorkflowEngine:
    """工作流执行引擎"""

    def __init__(self):
        self._step_results: Dict[str, WorkflowStepResult] = {}

    def execute(self, workflow_spec, context: ExecutionContext) -> str:
        """
        执行工作流

        Args:
            workflow_spec: 工作流规格
            context: 执行上下文

        Returns:
            str: 执行结果
        """
        self._step_results = {}
        results = []

        agent_logger.info(f"执行工作流: {workflow_spec.name} ({len(workflow_spec.steps)} 步)")

        # 构建依赖图
        step_map = {step.name: step for step in workflow_spec.steps}
        dependency_graph = self._build_dependency_graph(workflow_spec.steps)

        # 拓扑排序
        sorted_steps = self._topological_sort(step_map, dependency_graph)

        if sorted_steps is None:
            return "❌ 工作流存在循环依赖"

        # 执行步骤
        for step_name in sorted_steps:
            step = step_map[step_name]

            # 检查依赖是否完成
            if not self._check_dependencies(step, dependency_graph):
                results.append(f"[{step_name}] ❌ 依赖步骤未完成")
                continue

            # 检查条件
            if step.condition and not self._evaluate_condition(step.condition, context):
                results.append(f"[{step_name}] ⏭️ 条件不满足，跳过")
                continue

            # 执行步骤
            result = self._execute_step(step, context)
            results.append(f"[{step_name}] {result.result}")

            # 保存步骤结果
            self._step_results[step_name] = result

            # 如果步骤失败，根据配置决定是否继续
            if not result.success:
                if workflow_spec.config.get("stop_on_error", True):
                    agent_logger.warning(f"工作流在 {step_name} 停止")
                    break

        return "\n".join(results)

    def _build_dependency_graph(self, steps) -> Dict[str, Set[str]]:
        """构建依赖图"""
        graph = {}
        for step in steps:
            graph[step.name] = set(step.depends_on or [])
        return graph

    def _topological_sort(self, step_map: Dict, graph: Dict[str, Set[str]]) -> Optional[List[str]]:
        """拓扑排序"""
        visited = set()
        temp_mark = set()
        result = []

        def visit(node: str):
            if node in temp_mark:
                return False  # 循环依赖
            if node in visited:
                return True

            temp_mark.add(node)
            for dep in graph.get(node, []):
                if dep not in step_map:
                    continue  # 依赖不存在，跳过
                if not visit(dep):
                    return False
            temp_mark.remove(node)
            visited.add(node)
            result.append(node)
            return True

        for node in step_map.keys():
            if node not in visited:
                if not visit(node):
                    return None

        return result

    def _check_dependencies(self, step, graph: Dict[str, Set[str]]) -> bool:
        """检查依赖是否完成"""
        if not step.depends_on:
            return True

        for dep in step.depends_on:
            if dep not in self._step_results:
                return False
            if not self._step_results[dep].success:
                return False

        return True

    def _evaluate_condition(self, condition: str, context: ExecutionContext) -> bool:
        """评估条件表达式"""
        try:
            # 支持简单的条件检查
            if condition.startswith("state."):
                key = condition[6:]
                value = context.get_state(key)
                return bool(value)
            return True
        except Exception:
            return True

    def _execute_step(self, step, context: ExecutionContext) -> WorkflowStepResult:
        """执行单个步骤"""
        agent_logger.info(f"  执行步骤: {step.name} (技能: {step.skill})")

        # 获取技能规格
        skill_spec = skill_registry.get(step.skill)
        if not skill_spec:
            return WorkflowStepResult(
                step_name=step.name,
                success=False,
                result=f"❌ 技能 {step.skill} 不存在",
                error=f"Skill not found: {step.skill}"
            )

        # 获取技能处理器
        handler = skill_registry.get_handler(step.skill)
        if not handler:
            return WorkflowStepResult(
                step_name=step.name,
                success=False,
                result=f"❌ 技能 {step.skill} 未实现",
                error=f"Skill handler not found: {step.skill}"
            )

        # 准备子上下文
        sub_context = ExecutionContext(
            user_input=context.user_input,
            route_result={"type": "skill", "target": step.skill},
            state=context.state.copy(),
        )
        sub_context.current_workflow = context.current_workflow
        sub_context.current_step = step.name
        sub_context.current_skill = step.skill

        # 传递参数
        if step.params:
            for key, value in step.params.items():
                sub_context.set_state(key, value)

        try:
            # 执行技能
            result = handler(sub_context)

            # 收集输出
            outputs = {
                "result": result,
                "step_name": step.name,
            }

            # 从上下文中提取结果
            if sub_context.results:
                outputs.update(sub_context.results)

            success = "❌" not in result

            return WorkflowStepResult(
                step_name=step.name,
                success=success,
                result=result,
                outputs=outputs,
            )
        except Exception as e:
            error_msg = str(e)
            agent_logger.error(f"步骤 {step.name} 执行失败: {error_msg}")
            return WorkflowStepResult(
                step_name=step.name,
                success=False,
                result=f"❌ {error_msg}",
                error=error_msg,
            )