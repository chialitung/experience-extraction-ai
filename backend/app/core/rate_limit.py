"""基于内存的滑动窗口限流中间件。"""

import time
from typing import Dict, Tuple, Optional, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging import get_logger

logger = get_logger("app.rate_limit")


class SlidingWindowRateLimiter:
    """滑动窗口限流器（按客户端 IP）。"""

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: float = 60.0,
        block_seconds: float = 60.0,
        exclude_paths: Optional[list] = None,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self.exclude_paths = set(exclude_paths or ["/health", "/", "/docs", "/openapi.json"])
        # client_ip -> [(timestamp, count), ...]
        self._windows: Dict[str, list[Tuple[float, int]]] = {}
        # client_ip -> blocked_until
        self._blocked: Dict[str, float] = {}

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP。"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_excluded(self, path: str) -> bool:
        for p in self.exclude_paths:
            if p == "/" and path == "/":
                return True
            if p != "/" and path.startswith(p):
                return True
        return False

    def _cleanup(self, ip: str, now: float) -> None:
        """清理过期的窗口记录。"""
        cutoff = now - self.window_seconds
        if ip in self._windows:
            self._windows[ip] = [(t, c) for t, c in self._windows[ip] if t > cutoff]
            if not self._windows[ip]:
                del self._windows[ip]

    def _is_blocked(self, ip: str, now: float) -> bool:
        if ip in self._blocked:
            if now < self._blocked[ip]:
                return True
            del self._blocked[ip]
        return False

    def _check_and_record(self, ip: str, now: float) -> Tuple[bool, int]:
        """检查是否允许请求，返回 (allowed, remaining)。"""
        self._cleanup(ip, now)

        if self._is_blocked(ip, now):
            return False, 0

        window = self._windows.get(ip, [])
        total = sum(c for _, c in window)

        if total >= self.max_requests:
            # 触发限流，加入黑名单
            self._blocked[ip] = now + self.block_seconds
            return False, 0

        # 记录本次请求
        if window and now - window[-1][0] < 1.0:
            # 同一秒内，合并计数
            window[-1] = (window[-1][0], window[-1][1] + 1)
        else:
            window.append((now, 1))
        self._windows[ip] = window

        remaining = self.max_requests - total - 1
        return True, max(0, remaining)

    def is_allowed(self, request: Request) -> Tuple[bool, int, int]:
        """
        检查请求是否被允许。
        返回: (allowed, remaining_seconds, remaining_requests)
        """
        path = request.url.path
        if self._is_excluded(path):
            return True, 0, self.max_requests

        ip = self._get_client_ip(request)
        now = time.time()
        allowed, remaining = self._check_and_record(ip, now)

        if not allowed:
            retry_after = int(self._blocked.get(ip, now) - now)
            return False, retry_after, 0

        return True, 0, remaining


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI 限流中间件。"""

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = 60,
        window_seconds: float = 60.0,
        block_seconds: float = 60.0,
        exclude_paths: Optional[list] = None,
    ):
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter(
            max_requests=max_requests,
            window_seconds=window_seconds,
            block_seconds=block_seconds,
            exclude_paths=exclude_paths,
        )

    async def dispatch(self, request: Request, call_next: Callable):
        allowed, retry_after, remaining = self.limiter.is_allowed(request)
        client_ip = self.limiter._get_client_ip(request)
        path = request.url.path

        if not allowed:
            logger.warning(
                f"Rate limit triggered for {client_ip} on {path}",
                extra={
                    "client_ip": client_ip,
                    "path": path,
                    "method": request.method,
                    "retry_after": retry_after,
                    "event": "rate_limit_triggered",
                },
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "请求过于频繁，请稍后再试",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.limiter.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
