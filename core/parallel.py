# core/parallel.py
"""
并行执行器 - 处理无依赖的并行任务
"""

import time
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from core.logger import agent_logger
from core.context import ExecutionContext


@dataclass
class ParallelTask:
    """并行任务"""
    id: str
    name: str
    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    timeout: int = 30


@dataclass
class ParallelResult:
    """并行结果"""
    task_id: str
    success: bool
    result: Any = None
    error: str = None
    duration: float = 0.0


class ParallelExecutor:
    """并行执行器"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._executor = None

    def _get_executor(self):
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._executor

    def execute(self, tasks: List[ParallelTask], context: ExecutionContext) -> List[ParallelResult]:
        """
        并行执行多个任务

        Args:
            tasks: 任务列表
            context: 执行上下文

        Returns:
            List[ParallelResult]: 结果列表
        """
        if not tasks:
            return []

        # 构建依赖图
        task_map = {t.id: t for t in tasks}
        dependency_graph = self._build_dependency_graph(tasks)

        # 找出可并行执行的任务（无依赖的）
        ready_tasks = [t for t in tasks if not dependency_graph.get(t.id, [])]

        if not ready_tasks:
            agent_logger.warning("没有可并行执行的任务（所有任务都有依赖）")
            return [self._execute_single(t, context) for t in tasks]

        agent_logger.info(f"并行执行 {len(ready_tasks)} 个任务 (总任务: {len(tasks)})")

        executor = self._get_executor()
        futures = {}
        results_map = {}
        start_time = time.time()

        # 提交并行任务
        for task in ready_tasks:
            future = executor.submit(self._execute_single, task, context)
            futures[future] = task
            agent_logger.debug(f"提交并行任务: {task.name} (ID: {task.id})")

        # 收集结果
        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result(timeout=task.timeout)
                results_map[task.id] = result
            except Exception as e:
                agent_logger.error(f"并行任务失败 {task.name}: {e}")
                results_map[task.id] = ParallelResult(
                    task_id=task.id,
                    success=False,
                    error=str(e),
                )

        # 按原顺序返回结果
        results = [results_map.get(t.id) for t in tasks]

        duration = time.time() - start_time
        agent_logger.info(f"并行执行完成，耗时: {duration:.2f}s")

        return results

    def _execute_single(self, task: ParallelTask, context: ExecutionContext) -> ParallelResult:
        """执行单个任务"""
        start_time = time.time()
        try:
            result = task.func(*task.args, **task.kwargs)
            duration = time.time() - start_time
            return ParallelResult(
                task_id=task.id,
                success=True,
                result=result,
                duration=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            agent_logger.error(f"任务执行失败 {task.name}: {e}")
            return ParallelResult(
                task_id=task.id,
                success=False,
                error=str(e),
                duration=duration,
            )

    def _build_dependency_graph(self, tasks: List[ParallelTask]) -> Dict[str, List[str]]:
        """构建依赖图"""
        graph = {}
        for task in tasks:
            graph[task.id] = [dep for dep in task.dependencies if dep in {t.id for t in tasks}]
        return graph

    def shutdown(self):
        """关闭执行器"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
            agent_logger.debug("并行执行器已关闭")


# 全局并行执行器
parallel_executor = ParallelExecutor()