# api/routes/skills.py
"""技能路由"""

import time
from typing import List
from fastapi import APIRouter, HTTPException

from skills.registry import skill_registry
from core.session import session_manager
from core.context import ExecutionContext
from api.models.schemas import SkillInfo, SkillExecuteRequest, SkillExecuteResponse

router = APIRouter()


@router.get("/skills", response_model=List[SkillInfo])
async def list_skills():
    """列出所有技能"""
    skills = []
    for name, spec in skill_registry._items.items():
        # ✅ 计算 display_name：取第一个触发词，如果没有则用 name
        display_name = spec.triggers[0] if spec.triggers else name
        skills.append({
            "name": name,
            "display_name": display_name,
            "description": spec.description,
            "enabled": spec.enabled,
            "triggers": spec.triggers,
            "model": spec.model,
            "tools": spec.tools or [],
        })
    return skills


@router.post("/skills/{skill_name}", response_model=SkillExecuteResponse)
async def execute_skill(skill_name: str, request: SkillExecuteRequest):
    """执行指定技能"""
    start_time = time.time()

    try:
        # 检查技能是否存在
        spec = skill_registry.get(skill_name)
        if not spec:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        if not spec.enabled:
            raise HTTPException(status_code=403, detail=f"Skill '{skill_name}' is disabled")

        # 获取技能处理器
        handler = skill_registry.get_handler(skill_name)
        if not handler:
            raise HTTPException(status_code=500, detail=f"Skill '{skill_name}' has no handler")

        # 创建会话
        session = session_manager.get_or_create(request.session_id)

        # 构建上下文
        context = ExecutionContext(user_input=request.user_input)
        context.current_skill = skill_name
        context.route_result = {"type": "skill", "target": skill_name}

        # 执行技能
        result = handler(context)

        duration = time.time() - start_time

        return {
            "skill": skill_name,
            "success": "✅" in result,
            "result": result,
            "duration": duration,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))