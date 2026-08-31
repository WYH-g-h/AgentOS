# api/routes/health.py
"""健康检查路由"""

from fastapi import APIRouter

from core.health import health_check
from core.config import config
from core.unified_memory import unified
from tools.registry import tool_registry
from skills.registry import skill_registry
from workflows.registry import workflow_registry
from api.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """获取系统健康状态"""
    status = health_check.get_status_summary()

    return {
        "status": "ok" if status.get("ollama_running") else "degraded",
        "ollama": status.get("ollama_running", False),
        "ollama_url": status.get("base_url", "http://localhost:11434"),
        "models": status.get("model_count", 0),
        "tools": tool_registry.count(),
        "skills": len(skill_registry._items),
        "workflows": len(workflow_registry._items),
        "memory": len(unified.get_all()),
        "version": config.get("version", "17.0.0"),
    }


@router.get("/health/models")
async def get_available_models():
    """获取可用模型列表"""
    models = health_check.get_available_models(force_refresh=True)
    return {
        "total": len(models),
        "models": models,
    }