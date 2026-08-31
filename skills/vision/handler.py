# skills/vision/handler.py
"""
视觉分析技能：分析图片内容
支持: 描述图片、识别物体、OCR文字识别
"""

import os
import re
import base64
from typing import Optional
from pathlib import Path

from core.logger import agent_logger
from core.parser import extract_filename
from core.health import health_check
from core.config import config
from models.manager import model_manager
from skills.registry import skill_registry
from tools.registry import tool_registry

# ============================================================
# 配置
# ============================================================

# 图片搜索路径（从配置读取，否则使用默认值）
DEFAULT_SEARCH_PATHS = [
    "./output",
    "./uploads",
    "./data/images",
    ".",
]

# 支持的图片格式
SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}

# 视觉模型关键词
VISION_MODEL_KEYWORDS = ['llava', 'bakllava', 'cogvlm', 'qwen-vl', 'minicpm-v']


def _get_search_paths() -> list:
    """获取图片搜索路径"""
    # 尝试从技能配置读取
    skill_spec = skill_registry.get("vision")
    if skill_spec and hasattr(skill_spec, 'config'):
        paths = skill_spec.config.get("search_paths", [])
        if paths:
            return paths
    return DEFAULT_SEARCH_PATHS


def _find_image_file(filename: str) -> Optional[str]:
    """
    在多个路径中查找图片文件

    Args:
        filename: 文件名或路径

    Returns:
        str: 完整路径，未找到返回 None
    """
    if not filename:
        return None

    # 如果已经是完整路径且存在
    if os.path.exists(filename):
        return os.path.abspath(filename)

    # 在各搜索路径中查找
    search_paths = _get_search_paths()

    for search_path in search_paths:
        full_path = os.path.join(search_path, filename)
        if os.path.exists(full_path):
            return os.path.abspath(full_path)

        # 递归搜索（限制深度2层）
        try:
            for root, dirs, files in os.walk(search_path):
                if filename in files:
                    return os.path.abspath(os.path.join(root, filename))
                # 深度限制
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
    if ext not in SUPPORTED_EXTENSIONS:
        return False

    try:
        size = os.path.getsize(path)
        return size >= 1024  # 至少 1KB
    except Exception:
        return False


def _get_vision_model():
    """获取可用的视觉模型"""
    # 从技能配置读取默认模型
    skill_spec = skill_registry.get("vision")
    default_model = "llava:7b"

    if skill_spec:
        if skill_spec.model:
            default_model = skill_spec.model
        if hasattr(skill_spec, 'config'):
            default_model = skill_spec.config.get("default_model", default_model)

    # 先尝试默认模型
    model = model_manager.get_model(default_model)
    if model:
        return model, default_model

    # 尝试备用模型
    fallback_models = []
    if skill_spec and hasattr(skill_spec, 'config'):
        fallback_models = skill_spec.config.get("fallback_models", [])

    if not fallback_models:
        fallback_models = ["bakllava:7b", "llava:13b", "cogvlm"]

    for model_name in fallback_models:
        model = model_manager.get_model(model_name)
        if model:
            agent_logger.info(f"使用备用视觉模型: {model_name}")
            return model, model_name

    return None, None


def handler(context) -> str:
    """视觉分析技能实现"""
    agent_logger.info(f"执行视觉分析技能: {context.user_input[:50]}...")

    # ============================================================
    # 获取模型
    # ============================================================

    model, model_name = _get_vision_model()
    if not model:
        return (
            f"❌ 视觉模型不可用，请安装: ollama pull llava:7b\n"
            f"   可用视觉模型: {', '.join(VISION_MODEL_KEYWORDS)}"
        )

    # ============================================================
    # 提取图片文件名
    # ============================================================

    # 方式1: 使用 extract_filename
    target_file = extract_filename(context.user_input)

    # 方式2: 正则匹配图片格式
    if not target_file:
        img_match = re.search(
            r'([a-zA-Z0-9_\-\.]+\.(?:png|jpg|jpeg|gif|webp|bmp))',
            context.user_input,
            re.IGNORECASE
        )
        if img_match:
            target_file = img_match.group(1)

    # 方式3: 从会话状态获取
    if not target_file:
        target_file = context.get_state("image_path")

    if not target_file:
        return (
            "❌ 请指定图片文件名\n\n"
            "示例:\n"
            "  - [vision] image.png\n"
            "  - 【看图】photo.jpg\n"
            "  - (识图) screenshot.png"
        )

    # ============================================================
    # 查找图片
    # ============================================================

    full_path = _find_image_file(target_file)
    if not full_path:
        search_paths = _get_search_paths()
        return (
            f"❌ 图片不存在: {target_file}\n"
            f"搜索路径: {', '.join(search_paths)}"
        )

    if not _is_valid_image(full_path):
        return f"❌ 无效的图片文件: {target_file}"

    agent_logger.debug(f"找到图片: {full_path}")

    # ============================================================
    # 提取用户问题（删除硬编码触发词）
    # ============================================================

    user_question = context.user_input

    # 只移除文件名
    user_question = re.sub(r'[a-zA-Z0-9_\-\.]+\.\w+', '', user_question)
    user_question = user_question.strip()

    if not user_question:
        user_question = "请详细描述这张图片的内容，用中文回答。"

    # ============================================================
    # 调用视觉模型
    # ============================================================

    try:
        if hasattr(model, 'vision'):
            result = model.vision(full_path, user_question)
        else:
            # 尝试使用 LangChain 方式
            result = _call_vision_langchain(full_path, user_question)

        if not result:
            return "❌ 视觉分析返回空结果"

        if result.startswith("❌"):
            return result

        # 获取相对路径显示
        display_path = os.path.basename(full_path)
        return f"🖼️ 图片分析 ({display_path}) [{model_name}]:\n\n{result}"

    except Exception as e:
        agent_logger.error(f"视觉分析失败: {e}")
        return f"❌ 视觉分析失败: {e}"


def _call_vision_langchain(image_path: str, prompt: str) -> str:
    """
    使用 LangChain 调用视觉模型
    """
    try:
        from langchain_ollama import ChatOllama
        import base64

        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        from langchain_core.messages import HumanMessage

        model = ChatOllama(model="llava:7b")
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_data}"}
            ]
        )

        response = model.invoke([message])
        return response.content

    except Exception as e:
        agent_logger.warning(f"LangChain 视觉调用失败: {e}")
        return _call_vision_direct_api(image_path, prompt)


def _call_vision_direct_api(image_path: str, prompt: str) -> str:
    """
    直接调用 Ollama API
    """
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