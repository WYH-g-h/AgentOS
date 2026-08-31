# api/routes/tools.py
"""工具路由"""

import time
from typing import List
from fastapi import APIRouter, HTTPException

from tools.registry import tool_registry
from core.router import router as agent_router
from api.models.schemas import ToolInfo, ToolExecuteRequest, ToolExecuteResponse

router = APIRouter()


@router.get("/tools", response_model=List[ToolInfo])
async def list_tools():
    """列出所有工具"""
    tools = []
    for spec in tool_registry.list_all():
        # ✅ 从 router 获取中文别名，如果没有则使用 name
        display_name = agent_router.TOOL_ALIASES.get(spec.name, spec.name)
        tools.append({
            "name": spec.name,
            "display_name": display_name,
            "description": spec.description,
        })
    return tools


@router.post("/tools/{tool_name}", response_model=ToolExecuteResponse)
async def execute_tool(tool_name: str, request: ToolExecuteRequest):
    """执行指定工具"""
    start_time = time.time()

    try:
        # 检查工具是否存在
        spec = tool_registry.get(tool_name)
        if not spec:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        # 执行工具
        result = tool_registry.execute(tool_name, **request.params)

        duration = time.time() - start_time

        return {
            "tool": tool_name,
            "success": "✅" in result,
            "result": result,
            "duration": duration,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))