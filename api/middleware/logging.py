# api/middleware/logging.py
"""请求日志中间件"""

import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.logger import agent_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 记录请求
        agent_logger.debug(f"API Request: {request.method} {request.url.path}")

        response = await call_next(request)

        # 记录响应
        duration = time.time() - start_time
        agent_logger.debug(
            f"API Response: {request.method} {request.url.path} "
            f"→ {response.status_code} ({duration:.3f}s)"
        )

        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        return response