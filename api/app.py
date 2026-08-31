# api/app.py
"""
AgentOS REST API Server
提供 HTTP 接口访问 AgentOS 核心功能
"""

import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config import config
from core.logger import agent_logger
from core.health import health_check
from core.executor import Executor, ExecutorConfig
from core.session import session_manager
from core.router import router
from core.paths import get_skills_dir, get_workflows_dir, ensure_directories, PROJECT_ROOT

# 导入路由
from api.routes import chat, tools, skills, workflows, memory, rag, vision, health
from api.routes import admin
from api.middleware.logging import LoggingMiddleware


# ============================================================
# 生命周期管理
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("=" * 50)
    print("🚀 AgentOS API Server 启动中...")
    print("=" * 50)

    # ✅ 确保目录存在
    ensure_directories()

    # 初始化 AgentOS
    try:
        from models.registry import model_registry
        from tools.registry import tool_registry
        from skills.loader import load_skills
        from workflows.loader import load_workflows

        model_registry.load_defaults()

        # ✅ 使用统一路径
        skills_dir = get_skills_dir()
        workflows_dir = get_workflows_dir()

        if skills_dir.exists():
            load_skills(str(skills_dir))
            print(f"  ✅ 技能目录: {skills_dir}")
        else:
            print(f"  ⚠️ 技能目录不存在: {skills_dir}")

        if workflows_dir.exists():
            load_workflows(str(workflows_dir))
            print(f"  ✅ 工作流目录: {workflows_dir}")
        else:
            print(f"  ⚠️ 工作流目录不存在: {workflows_dir}")

        router.refresh_route_map()

        print(f"  ✅ 工具: {tool_registry.count()} 个")

        # 检查 Ollama
        status = health_check.get_status_summary()
        if status.get("ollama_running"):
            print(f"  ✅ Ollama: 运行中 ({status.get('model_count', 0)} 个模型)")

            try:
                available_models = health_check.get_available_models(force_refresh=True)
                model_names = [m.get("name", "") for m in available_models]

                vision_models = ["llava:7b", "bakllava:7b", "llava:13b", "cogvlm"]
                found = False
                for vm in vision_models:
                    if vm in model_names:
                        print(f"  ✅ 视觉模型: {vm} 已安装")
                        found = True
                        break

                if not found:
                    print(f"  ⚠️ 视觉模型未安装 (推荐: ollama pull llava:7b)")
            except Exception as e:
                print(f"  ⚠️ 视觉模型检查失败: {e}")
        else:
            print("  ⚠️ Ollama: 不可用")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        raise

    print("=" * 50)
    print("✅ AgentOS API Server 就绪")
    print(f"📍 访问: http://{config.get('api.host', '127.0.0.1')}:{config.get('api.port', 8000)}")
    print(f"📖 文档: http://{config.get('api.host', '127.0.0.1')}:{config.get('api.port', 8000)}/docs")
    print("=" * 50)

    yield

    print("👋 AgentOS API Server 关闭")


# ============================================================
# 创建 FastAPI 应用
# ============================================================

app = FastAPI(
    title="AgentOS API",
    description="AgentOS L3 组件化 Agent API",
    version="17.0.0",
    lifespan=lifespan,
)

# ============================================================
# ✅ 注册日志中间件
# ============================================================

app.add_middleware(LoggingMiddleware)

# ============================================================
# ✅ CORS 配置（从配置文件读取）
# ============================================================

cors_origins = config.get(
    "api.cors_origins",
    [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8501",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8501",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ✅ 全局异常处理器
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    agent_logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if config.get("api.debug", False) else None,
        }
    )


# ============================================================
# 注册路由
# ============================================================

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(tools.router, prefix="/api", tags=["tools"])
app.include_router(skills.router, prefix="/api", tags=["skills"])
app.include_router(workflows.router, prefix="/api", tags=["workflows"])
app.include_router(memory.router, prefix="/api", tags=["memory"])
app.include_router(rag.router, prefix="/api", tags=["rag"])
app.include_router(vision.router, prefix="/api", tags=["vision"])
app.include_router(admin.router, prefix="/api", tags=["admin"])  # ✅ 注册 admin 路由


# ============================================================
# 根路径
# ============================================================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "AgentOS API",
        "version": "17.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/health",
        "routes": {
            "chat": "/api/chat",
            "tools": "/api/tools",
            "skills": "/api/skills",
            "workflows": "/api/workflows",
            "memory": "/api/memory",
            "rag": "/api/rag",
            "vision": "/api/vision",
            "health": "/api/health",
            "admin": "/api/admin",
        }
    }


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    host = config.get("api.host", "127.0.0.1")
    port = config.get("api.port", 8000)
    debug = config.get("api.debug", True)

    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if debug else "warning",
    )