# api/routes/chat.py
"""对话路由"""

import time
import json
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.executor import Executor, ExecutorConfig
from core.context import ExecutionContext
from core.session import session_manager
from core.router import router as agent_router
from core.memory_layer import memory_layer
from models.manager import model_manager
from api.models.schemas import ChatRequest, ChatResponse, ChatStreamChunk
from core.logger import agent_logger

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送消息到 AgentOS（非流式）"""
    try:
        start_time = time.time()

        session = session_manager.get_or_create(request.session_id)

        context = ExecutionContext(user_input=request.user_input)
        context.set_state("session_id", session.session_id)

        route_result = agent_router.route(request.user_input, session)
        context.route_result = {
            "type": route_result.type,
            "target": route_result.target,
            "confidence": route_result.confidence,
            "reason": route_result.reason,
            "args": route_result.args,
            "metadata": route_result.metadata or {}
        }

        executor = Executor(ExecutorConfig(max_retries=3))
        result = executor.execute(context)

        session.add_message("user", request.user_input)
        session.add_message("assistant", result)

        duration = time.time() - start_time

        return ChatResponse(
            response=result,
            session_id=session.session_id,
            route=context.route_result,
            duration=duration,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    try:
        session = session_manager.get_or_create(request.session_id)
        context = ExecutionContext(user_input=request.user_input)
        context.set_state("session_id", session.session_id)

        route_result = agent_router.route(request.user_input, session)
        context.route_result = {
            "type": route_result.type,
            "target": route_result.target,
            "confidence": route_result.confidence,
            "reason": route_result.reason,
            "args": route_result.args,
            "metadata": route_result.metadata or {}
        }

        async def generate() -> AsyncGenerator[str, None]:
            try:
                route_type = context.route_result.get("type", "chat")

                if route_type in ["tool", "skill", "workflow"]:
                    executor = Executor(ExecutorConfig(max_retries=3))
                    result = executor.execute(context)
                    yield json.dumps({"content": result, "done": True, "session_id": session.session_id}) + "\n"
                    return

                doer = model_manager.get_doer()
                if not doer:
                    yield json.dumps({"content": "❌ 模型未配置", "done": True, "session_id": session.session_id}) + "\n"
                    return

                messages = session.get_messages()
                if messages:
                    context_str = session.get_context()
                    if context_str:
                        enhanced_input = f"{request.user_input}\n\n[对话历史]\n{context_str}"
                    else:
                        enhanced_input = request.user_input
                else:
                    enhanced_input = request.user_input

                full_response = ""

                # ✅ 统一使用 invoke（ChatOllama 只有 invoke）
                try:
                    result = doer.invoke(enhanced_input)
                    full_response = result.content if result and hasattr(result, 'content') else str(result)
                    yield json.dumps({"content": full_response, "done": True, "session_id": session.session_id}) + "\n"
                except Exception as e:
                    yield json.dumps({"content": f"❌ 调用失败: {e}", "done": True, "session_id": session.session_id}) + "\n"
                    return

                session.add_message("user", request.user_input)
                if full_response:
                    session.add_message("assistant", full_response)

                doer = model_manager.get_doer()
                agent_logger.info(f"Doer type: {type(doer)}")
                agent_logger.info(f"Doer methods: {[m for m in dir(doer) if not m.startswith('_')]}")

            except Exception as e:
                agent_logger.error(f"流式生成失败: {e}")
                yield json.dumps({"content": f"❌ 错误: {str(e)}", "done": True, "session_id": session.session_id}) + "\n"

        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Session-Id": session.session_id,
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))