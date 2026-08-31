# core/queue.py
"""
任务队列：异步执行长时间任务
"""

import threading
import queue
import time
import uuid
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .logger import agent_logger


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class Task:
    """任务对象"""
    id: str
    name: str
    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    progress_message: str = ""


class TaskQueue:
    """任务队列（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._queue: queue.Queue = queue.Queue()
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._initialized = True

        # 启动工作线程
        self._start_worker()

    def _start_worker(self):
        """启动工作线程"""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._running = True
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()
            agent_logger.info("任务队列工作线程已启动")

    def _worker_loop(self):
        """工作线程主循环"""
        while self._running:
            try:
                task_id = self._queue.get(timeout=1)
                self._execute_task(task_id)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                agent_logger.error(f"任务执行异常: {e}")

    def _execute_task(self, task_id: str):
        """执行单个任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return

            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

        agent_logger.info(f"执行任务: {task.name} (ID: {task_id[:8]})")

        try:
            result = task.func(*task.args, **task.kwargs)

            with self._lock:
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now()
                task.progress = 1.0

            agent_logger.info(f"任务完成: {task.name} (ID: {task_id[:8]})")

        except Exception as e:
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now()

            agent_logger.error(f"任务失败: {task.name} - {e}")

    def submit(self, name: str, func: Callable, *args, **kwargs) -> str:
        """
        提交任务到队列

        Returns:
            task_id: 任务ID
        """
        task_id = uuid.uuid4().hex[:16]
        task = Task(
            id=task_id,
            name=name,
            func=func,
            args=args,
            kwargs=kwargs,
        )

        with self._lock:
            self._tasks[task_id] = task

        self._queue.put(task_id)
        agent_logger.debug(f"任务已提交: {name} (ID: {task_id[:8]})")
        return task_id

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            return {
                "id": task.id,
                "name": task.name,
                "status": task.status.value,
                "progress": task.progress,
                "progress_message": task.progress_message,
                "result": task.result if task.status == TaskStatus.COMPLETED else None,
                "error": task.error if task.status == TaskStatus.FAILED else None,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }

    def get_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[Any]:
        """等待并获取任务结果"""
        start = time.time()
        while True:
            status = self.get_status(task_id)
            if not status:
                return None

            if status["status"] == TaskStatus.COMPLETED.value:
                return status["result"]
            elif status["status"] == TaskStatus.FAILED.value:
                raise Exception(status["error"])
            elif status["status"] == TaskStatus.CANCELLED.value:
                return None

            if timeout and time.time() - start > timeout:
                raise TimeoutError(f"任务 {task_id} 超时")

            time.sleep(0.5)

    def cancel(self, task_id: str) -> bool:
        """取消任务（仅限待执行状态）"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                agent_logger.info(f"任务已取消: {task.name} (ID: {task_id[:8]})")
                return True

            return False

    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有任务"""
        tasks = []
        with self._lock:
            for task in self._tasks.values():
                if status and task.status.value != status:
                    continue
                tasks.append({
                    "id": task.id[:8],
                    "name": task.name,
                    "status": task.status.value,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                })
        return tasks

    def clear_completed(self):
        """清理已完成的任务"""
        with self._lock:
            to_remove = []
            for task_id, task in self._tasks.items():
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]

            agent_logger.info(f"清理了 {len(to_remove)} 个已完成的任务")

    def stop(self):
        """停止工作线程"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2)


# 全局任务队列实例
task_queue = TaskQueue()


# ============================================================
# 装饰器：异步执行
# ============================================================

def async_task(name: str = None):
    """
    装饰器：将函数作为异步任务执行

    Example:
        @async_task("总结文件")
        def summarize_file(filepath):
            return do_summarize(filepath)

        # 调用
        task_id = summarize_file("test.txt")
        result = task_queue.get_result(task_id)
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            task_name = name or func.__name__
            return task_queue.submit(task_name, func, *args, **kwargs)

        return wrapper

    return decorator