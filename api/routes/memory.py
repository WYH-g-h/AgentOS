# api/routes/memory.py
"""记忆路由"""

import os
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException,Body
from datetime import datetime

from core.unified_memory import unified
from core.memory_layer import memory_layer
from core.paths import get_memory_dir
from api.models.schemas import (
    MemoryListResponse,
    MemoryItem,
    MemoryAddRequest,
    MemoryAddResponse,
)

router = APIRouter()


@router.get("/memory", response_model=MemoryListResponse)
async def get_memory():
    """获取所有会话列表"""
    chats_dir = get_memory_dir()
    chat_items = []

    if chats_dir.exists():
        for chat_file in chats_dir.glob("*.json"):
            try:
                with open(chat_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    session_id = chat_file.stem
                    messages = data.get("messages", [])

                    # ✅ 优先使用保存的 name，如果没有则从消息中提取
                    name = data.get("name", "")
                    if not name:
                        for msg in messages:
                            if msg.get("role") == "user":
                                content = msg.get("content", "")
                                if content:
                                    name = content[:30] + ("..." if len(content) > 30 else "")
                                    break
                        if not name:
                            name = "新会话"

                    chat_items.append(MemoryItem(
                        id=session_id,
                        content=name,
                        category="session",
                        display_name="会话",
                        time=data.get("created_at", data.get("updated_at", "")),
                    ))
            except Exception as e:
                print(f"读取会话文件失败 {chat_file}: {e}")

    # 按时间倒序排列
    chat_items.sort(key=lambda x: x.time, reverse=True)

    return {
        "total": len(chat_items),
        "items": chat_items,
    }


@router.get("/memory/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取指定会话的所有历史消息"""
    chats_dir = get_memory_dir()

    # ✅ 直接用 session_id 作为文件名
    filepath = chats_dir / f"{session_id}.json"

    print(f"🔍 查找会话: {session_id}")
    print(f"📄 文件路径: {filepath}, 存在: {filepath.exists()}")

    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = data.get("messages", [])
                print(f"✅ 读取到 {len(messages)} 条消息")

                result = []
                for msg in messages:
                    result.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", ""),
                    })

                return {
                    "session_id": session_id,
                    "messages": result,
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                }
        except Exception as e:
            print(f"❌ 读取失败: {e}")
            raise HTTPException(status_code=500, detail=f"读取会话失败: {e}")

    print(f"❌ 会话文件不存在: {filepath}")
    return {
        "session_id": session_id,
        "messages": [],
        "created_at": "",
        "updated_at": "",
    }


@router.get("/memory/profile")
async def get_profile():
    """获取用户画像"""
    return unified.get_profile()


@router.post("/memory", response_model=MemoryAddResponse)
async def add_memory(request: MemoryAddRequest):
    """添加记忆"""
    try:
        result = memory_layer.add_memory(
            request.content,
            "user_info",
            request.category or "general"
        )
        return {
            "success": "✅" in result,
            "message": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory/{item_id}")
async def delete_memory(item_id: str):
    """删除记忆"""
    try:
        chats_dir = get_memory_dir()
        chat_file = chats_dir / f"{item_id}.json"
        if chat_file.exists():
            chat_file.unlink()
            return {"success": True, "message": f"已删除会话 {item_id}"}

        result = unified.delete(item_id)
        return {"success": "✅" in result, "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/memory/{session_id}/rename")
async def rename_session(session_id: str, new_name: str = Body(..., embed=True)):
    """重命名会话"""
    chats_dir = get_memory_dir()
    filepath = chats_dir / f"{session_id}.json"

    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        data["name"] = new_name.strip()
        data["updated_at"] = datetime.now().isoformat()

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return {"success": True, "message": f"会话已重命名为 '{new_name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))