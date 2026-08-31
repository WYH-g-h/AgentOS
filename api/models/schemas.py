# api/models/schemas.py
"""
API 数据模型 (Pydantic)
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


# ============================================================
# 通用响应
# ============================================================

class BaseResponse(BaseModel):
    """基础响应"""
    success: bool = True
    message: str = ""
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str
    status_code: int
    detail: Optional[str] = None


# ============================================================
# 健康检查
# ============================================================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str  # ok, degraded, error
    ollama: bool
    ollama_url: str
    models: int
    tools: int
    skills: int
    workflows: int
    memory: int
    version: str


# ============================================================
# 对话
# ============================================================

class ChatRequest(BaseModel):
    """对话请求"""
    user_input: str = Field(..., description="用户输入")
    session_id: Optional[str] = Field(None, description="会话ID")
    stream: bool = Field(False, description="是否流式输出")


class ChatResponse(BaseModel):
    """对话响应"""
    response: str = Field(..., description="Agent回复")
    session_id: str = Field(..., description="会话ID")
    route: Dict[str, Any] = Field(default_factory=dict, description="路由信息")
    duration: Optional[float] = Field(None, description="耗时(秒)")


class ChatStreamChunk(BaseModel):
    """流式响应块"""
    content: str = Field(..., description="内容块")
    done: bool = Field(False, description="是否完成")
    session_id: Optional[str] = Field(None, description="会话ID")


# ============================================================
# 工具
# ============================================================

class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    display_name: Optional[str] = None
    description: str


class ToolExecuteRequest(BaseModel):
    """工具执行请求"""
    params: Dict[str, Any] = Field(default_factory=dict, description="工具参数")


class ToolExecuteResponse(BaseModel):
    """工具执行响应"""
    tool: str
    success: bool
    result: str
    duration: Optional[float] = None


# ============================================================
# 技能
# ============================================================

class SkillInfo(BaseModel):
    """技能信息"""
    name: str
    description: str
    enabled: bool
    triggers: List[str]
    model: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    display_name: Optional[str] = None


class SkillExecuteRequest(BaseModel):
    """技能执行请求"""
    user_input: str = Field(..., description="用户输入")
    session_id: Optional[str] = Field(None, description="会话ID")


class SkillExecuteResponse(BaseModel):
    """技能执行响应"""
    skill: str
    success: bool
    result: str
    duration: Optional[float] = None


# ============================================================
# 工作流
# ============================================================

class WorkflowInfo(BaseModel):
    """工作流信息"""
    name: str
    description: str
    enabled: bool
    steps: int
    triggers: List[str]
    display_name: Optional[str] = None


class WorkflowExecuteRequest(BaseModel):
    """工作流执行请求"""
    user_input: str = Field(..., description="用户输入")
    session_id: Optional[str] = Field(None, description="会话ID")


class WorkflowExecuteResponse(BaseModel):
    """工作流执行响应"""
    workflow: str
    success: bool
    result: str
    duration: Optional[float] = None


# ============================================================
# 记忆
# ============================================================

class MemoryItem(BaseModel):
    """记忆条目"""
    id: str
    content: str
    category: str
    display_name: str
    time: str


class MemoryListResponse(BaseModel):
    """记忆列表响应"""
    total: int
    items: List[MemoryItem]


class MemoryAddRequest(BaseModel):
    """添加记忆请求"""
    content: str = Field(..., description="记忆内容")
    category: Optional[str] = Field(None, description="分类")


class MemoryAddResponse(BaseModel):
    """添加记忆响应"""
    success: bool
    message: str


# ============================================================
# RAG
# ============================================================

class RAGSearchRequest(BaseModel):
    """RAG搜索请求"""
    query: str = Field(..., description="搜索内容")
    project: str = Field("default", description="项目名")
    k: int = Field(3, description="返回数量", ge=1, le=10)


class RAGSearchResponse(BaseModel):
    """RAG搜索响应"""
    success: bool
    result: str


class RAGAddRequest(BaseModel):
    """RAG添加请求"""
    project: str = Field("default", description="项目名")
    filepath: str = Field(..., description="文件路径")
    content: Optional[str] = Field(None, description="文件内容（可选，如果不提供则自动读取）")


# ============================================================
# 视觉
# ============================================================

class VisionRequest(BaseModel):
    """视觉分析请求"""
    image_path: str = Field(..., description="图片路径（支持相对路径和文件名）")
    prompt: Optional[str] = Field(None, description="分析提示，默认为'请描述这张图片的内容'")
    session_id: Optional[str] = Field(None, description="会话ID")


class VisionResponse(BaseModel):
    """视觉分析响应"""
    success: bool
    result: str
    image_path: str
    session_id: Optional[str] = Field(None, description="会话ID")
    duration: Optional[float] = Field(None, description="耗时(秒)")


class VisionUploadResponse(BaseModel):
    """图片上传响应"""
    success: bool
    filename: str
    saved_as: str
    path: str
    url: str
    message: str
    session_id: Optional[str] = None


# ============================================================
# 会话
# ============================================================

class SessionListResponse(BaseModel):
    """会话列表响应"""
    total: int
    sessions: List[str]


class SessionDeleteResponse(BaseModel):
    """会话删除响应"""
    success: bool
    message: str


# ============================================================
# 批量操作
# ============================================================

class BatchOperationResponse(BaseModel):
    """批量操作响应"""
    success: bool
    results: List[Dict[str, Any]]
    failed: int = 0
    total: int = 0