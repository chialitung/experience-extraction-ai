"""HTTP 请求日志中间件。

记录每条请求的 method、path、status_code、duration_ms、client_ip、request_id。
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging import get_logger, generate_request_id


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件：记录请求全链路信息。"""

    def __init__(
        self,
        app: ASGIApp,
    ):
        super().__init__(app)
        self.logger = get_logger("app.middleware")

    async def dispatch(self, request: Request, call_next: Callable):
        # 生成或复用 request_id
        request_id = request.headers.get("X-Request-ID", generate_request_id())
        request.state.request_id = request_id

        start_time = time.time()
        client_ip = self._get_client_ip(request)
        path = request.url.path
        method = request.method

        # 记录请求开始
        logger = get_logger("app.middleware", request_id=request_id)
        logger.info(
            f"HTTP request started",
            extra={
                "client_ip": client_ip,
                "method": method,
                "path": path,
                "query": str(request.query_params),
                "user_agent": request.headers.get("user-agent", ""),
                "event": "request_started",
            },
        )

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"HTTP request failed with exception: {exc}",
                extra={
                    "client_ip": client_ip,
                    "method": method,
                    "path": path,
                    "duration_ms": round(duration_ms, 2),
                    "status_code": 500,
                    "event": "request_exception",
                },
                exc_info=True,
            )
            raise

        duration_ms = (time.time() - start_time) * 1000
        status_code = response.status_code

        # 根据状态码选择日志级别
        log_extra = {
            "client_ip": client_ip,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "event": "request_completed",
        }

        if status_code >= 500:
            logger.error(f"HTTP request completed with server error", extra=log_extra)
        elif status_code >= 400:
            logger.warning(f"HTTP request completed with client error", extra=log_extra)
        else:
            logger.info(f"HTTP request completed", extra=log_extra)

        # 将 request_id 注入响应头，便于前端追踪
        response.headers["X-Request-ID"] = request_id
        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP。"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
