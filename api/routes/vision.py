# api/routes/vision.py
"""
视觉路由 - 图片分析
支持 JSON 和 Form 请求
"""

import sys
import time
import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from core.logger import agent_logger
from core.health import health_check
from core.session import session_manager
from core.config import config
from core.paths import get_project_root, get_uploads_dir, ensure_directories
from models.manager import model_manager
from api.models.schemas import VisionRequest, VisionResponse

router = APIRouter()

# ============================================================
# ✅ 兼容开发环境和打包环境的路径
# ============================================================

PROJECT_ROOT = get_project_root()
OUTPUT_DIR = PROJECT_ROOT / "output"

# ✅ 确保上传目录存在
ensure_directories()

IMAGE_SEARCH_PATHS = [
    str(PROJECT_ROOT / "output"),
    ".",
]

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}


def _find_image_file(filename: str) -> Optional[str]:
    """在多个路径中查找图片文件"""
    if os.path.exists(filename):
        return filename

    if os.path.sep in filename or '/' in filename:
        if os.path.exists(filename):
            return filename

    for search_path in IMAGE_SEARCH_PATHS:
        full_path = os.path.join(search_path, filename)
        if os.path.exists(full_path):
            return os.path.abspath(full_path)

        try:
            for root, dirs, files in os.walk(search_path):
                if filename in files:
                    return os.path.abspath(os.path.join(root, filename))
                depth = root.replace(search_path, '').count(os.sep)
                if depth > 2:
                    break
        except Exception:
            continue

    return None


def _is_valid_image(path: str) -> bool:
    """检查是否为有效的图片文件"""
    if not os.path.exists(path):
        return False

    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False

    try:
        size = os.path.getsize(path)
        return size >= 1024
    except Exception:
        return False


# ============================================================
# API 端点
# ============================================================

@router.post("/vision/analyze", response_model=VisionResponse)
async def analyze_image(request: VisionRequest):
    """分析图片内容（JSON 请求）"""
    start_time = time.time()

    try:
        session = session_manager.get_or_create(request.session_id)
        agent_logger.info(f"视觉分析: {request.image_path} (会话: {session.session_id})")

        full_path = _find_image_file(request.image_path)
        if not full_path:
            raise HTTPException(
                status_code=404,
                detail=f"图片不存在: {request.image_path}\n搜索路径: {', '.join(IMAGE_SEARCH_PATHS)}"
            )

        if not _is_valid_image(full_path):
            raise HTTPException(
                status_code=400,
                detail=f"无效的图片文件: {request.image_path}"
            )

        # ✅ 使用 health_check 获取可用模型列表
        available_models = health_check.get_available_models(force_refresh=True)
        model_names = [m.get("name", "") for m in available_models]

        vision_candidates = ["llava:7b", "bakllava:7b", "llava:13b", "cogvlm", "qwen-vl"]
        vision_model_name = None

        for candidate in vision_candidates:
            if candidate in model_names:
                vision_model_name = candidate
                break

        if not vision_model_name:
            raise HTTPException(
                status_code=503,
                detail="视觉模型不可用，请安装: ollama pull llava:7b"
            )

        vision_model = model_manager.get_model(vision_model_name)
        if not vision_model:
            raise HTTPException(
                status_code=503,
                detail=f"视觉模型 {vision_model_name} 加载失败"
            )

        agent_logger.info(f"使用视觉模型: {vision_model_name}")

        # ✅ 强制中文输出
        if request.prompt:
            prompt = request.prompt + " 请用中文回答。"
        else:
            prompt = "请详细描述这张图片的内容，用中文回答。"

        if hasattr(vision_model, 'vision'):
            result = vision_model.vision(full_path, prompt)
        else:
            result = _fallback_vision(full_path, prompt)

        duration = time.time() - start_time

        session.add_message("user", f"[视觉] {prompt}")
        session.add_message("assistant", result[:500] + "..." if len(result) > 500 else result)

        return VisionResponse(
            success=True,
            result=result,
            image_path=os.path.basename(full_path),
            session_id=session.session_id,
            duration=duration,
        )

    except HTTPException:
        raise
    except Exception as e:
        agent_logger.error(f"视觉分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vision/analyze-form")
async def analyze_image_form(
        image_path: str = Form(..., description="图片路径"),
        prompt: Optional[str] = Form(None, description="分析提示"),
        session_id: Optional[str] = Form(None, description="会话ID"),
):
    """分析图片内容（Form 请求）"""
    request = VisionRequest(
        image_path=image_path,
        prompt=prompt,
        session_id=session_id,
    )
    return await analyze_image(request)


@router.post("/vision/upload")
async def upload_image(
        file: UploadFile = File(..., description="图片文件"),
        session_id: Optional[str] = Form(None, description="会话ID"),
):
    """上传图片到 output 目录"""
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {ext}，支持: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # ✅ 保存到 output 目录
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 清理文件名
        import re
        clean_filename = re.sub(r'[^\w\-_.]', '_', file.filename)
        filepath = OUTPUT_DIR / clean_filename

        content = await file.read()

        max_size = config.get("vision.max_image_size", 10485760)
        if len(content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"图片太大：{len(content) / 1024 / 1024:.1f}MB，最大支持 {max_size / 1024 / 1024:.0f}MB"
            )

        with open(filepath, 'wb') as f:
            f.write(content)

        agent_logger.info(f"图片上传: {filepath}")

        return {
            "success": True,
            "filename": file.filename,
            "saved_as": clean_filename,
            "path": str(filepath),
            "url": f"/output/{clean_filename}",
            "message": f"已上传到 output/{clean_filename}",
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        agent_logger.error(f"图片上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vision/models")
async def list_vision_models():
    """列出可用的视觉模型"""
    try:
        from models.providers.ollama import OllamaProvider
        provider = OllamaProvider({"base_url": "http://localhost:11434"})
        models = provider.list_models()

        vision_models = []
        vision_keywords = ["llava", "bakllava", "cogvlm", "qwen-vl", "minicpm-v"]

        for m in models:
            name = m.get("name", "")
            for keyword in vision_keywords:
                if keyword in name.lower():
                    vision_models.append({
                        "name": name,
                        "size": m.get("size", 0),
                        "modified": m.get("modified_at", ""),
                        "keyword": keyword,
                    })
                    break

        return {
            "total": len(vision_models),
            "models": vision_models,
            "recommended": "llava:7b",
        }
    except Exception as e:
        return {"error": str(e), "models": []}


# ============================================================
# 降级方案
# ============================================================

def _fallback_vision(image_path: str, prompt: str) -> str:
    """降级方案：直接调用 Ollama API"""
    import base64
    import requests

    try:
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        payload = {
            "model": "llava:7b",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_data]
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 2048,
            }
        }

        resp = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            timeout=120
        )

        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "")
        else:
            return f"❌ 视觉模型调用失败: HTTP {resp.status_code}"

    except requests.ConnectionError:
        return "❌ Ollama 服务未运行，请先启动: ollama serve"
    except requests.Timeout:
        return "❌ 视觉分析超时，请检查模型是否已下载"
    except Exception as e:
        return f"❌ 视觉分析异常: {e}"

@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(..., description="文件"),
    session_id: Optional[str] = Form(None, description="会话ID"),
):
    """上传任意文件到 output 目录"""
    from core.paths import get_output_dir
    import re

    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    clean_filename = re.sub(r'[^\w\-_.]', '_', file.filename)
    filepath = output_dir / clean_filename

    content = await file.read()

    # 限制 100MB
    max_size = 100 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件太大，最大支持 100MB"
        )

    with open(filepath, 'wb') as f:
        f.write(content)

    return {
        "success": True,
        "filename": file.filename,
        "saved_as": clean_filename,
        "path": str(filepath),
        "size": len(content),
        "session_id": session_id,
    }