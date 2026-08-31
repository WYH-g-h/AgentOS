# api/routes/rag.py
"""RAG路由"""

from fastapi import APIRouter, HTTPException

from core.rag import rag
from api.models.schemas import RAGSearchRequest, RAGSearchResponse

router = APIRouter()


@router.get("/rag/projects")
async def list_rag_projects():
    """列出所有 RAG 项目"""
    projects = rag.list_projects()
    return {"projects": projects}


@router.post("/rag/search", response_model=RAGSearchResponse)
async def rag_search(request: RAGSearchRequest):
    """搜索 RAG 知识库"""
    try:
        result = rag.search(
            request.project,
            request.query,
            request.k
        )
        return {
            "success": bool(result),
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/ask", response_model=RAGSearchResponse)
async def rag_ask(request: RAGSearchRequest):
    """基于 RAG 问答"""
    try:
        result = rag.ask(request.project, request.query)
        return {
            "success": bool(result),
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/add")
async def rag_add(project: str = "default", filepath: str = ""):
    """添加文件到 RAG"""
    try:
        from tools.registry import tool_registry

        if not filepath:
            return {"success": False, "message": "请指定文件路径"}

        # 读取文件
        content = tool_registry.execute("read_file", filepath=filepath)
        if "❌" in content:
            return {"success": False, "message": content}

        rag.add(project, {filepath: content})
        return {"success": True, "message": f"已添加 {filepath} 到 RAG"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))