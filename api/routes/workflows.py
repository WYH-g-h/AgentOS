# api/routes/workflows.py
"""工作流路由"""

import time
from typing import List
from fastapi import APIRouter, HTTPException

from workflows.registry import workflow_registry
from core.executor import Executor, ExecutorConfig
from core.context import ExecutionContext
from core.session import session_manager
from api.models.schemas import WorkflowInfo, WorkflowExecuteRequest, WorkflowExecuteResponse

router = APIRouter()


@router.get("/workflows", response_model=List[WorkflowInfo])
async def list_workflows():
    """列出所有工作流"""
    workflows = []
    for name, spec in workflow_registry._items.items():
        # ✅ 计算 display_name：取第一个触发词，如果没有则用 name
        display_name = spec.triggers[0] if spec.triggers else name
        workflows.append({
            "name": name,
            "display_name": display_name,
            "description": spec.description,
            "enabled": spec.enabled,
            "steps": len(spec.steps),
            "triggers": spec.triggers,
        })
    return workflows


@router.post("/workflows/{workflow_name}", response_model=WorkflowExecuteResponse)
async def execute_workflow(workflow_name: str, request: WorkflowExecuteRequest):
    """执行指定工作流"""
    start_time = time.time()

    try:
        # 检查工作流是否存在
        spec = workflow_registry.get(workflow_name)
        if not spec:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found")

        if not spec.enabled:
            raise HTTPException(status_code=403, detail=f"Workflow '{workflow_name}' is disabled")

        # 创建会话
        session = session_manager.get_or_create(request.session_id)

        # 构建上下文
        context = ExecutionContext(user_input=request.user_input)
        context.current_workflow = workflow_name
        context.route_result = {"type": "workflow", "target": workflow_name}

        # 执行工作流
        executor = Executor(ExecutorConfig(max_retries=3))
        result = executor.execute(context)

        duration = time.time() - start_time

        return {
            "workflow": workflow_name,
            "success": "✅" in result,
            "result": result,
            "duration": duration,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))