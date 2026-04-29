from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import ValidationError
import traceback

from app.core.config import settings
from app.core.database import engine, Base
from app.core.rate_limit import RateLimitMiddleware
from app.core.middleware import RequestLoggingMiddleware
from app.core.logging import setup_logging, get_logger
from app.api.v1 import router as v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 初始化日志系统
    setup_logging()
    logger = get_logger("app.main")
    logger.info(f"Application starting up | env={settings.ENVIRONMENT} | debug={settings.DEBUG}")

    # 启动时创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # 关闭时清理资源
    logger.info("Application shutting down")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="AI驱动的经验萃取访谈辅助系统",
    version="0.1.0",
    lifespan=lifespan,
)

# 请求日志中间件（必须最先添加，确保捕获所有请求）
app.add_middleware(RequestLoggingMiddleware)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流中间件：每IP每分钟200次请求，触发后封禁30秒
# 注意：轮询端点（structured-content, expert-profile, analysis）已排除，不计入限流
app.add_middleware(
    RateLimitMiddleware,
    max_requests=200,
    window_seconds=60.0,
    block_seconds=30.0,
    exclude_paths=["/health", "/", "/docs", "/openapi.json",
                   "/api/v1/interviews/{interview_id}/structured-content",
                   "/api/v1/interviews/{interview_id}/expert-profile",
                   "/api/v1/interviews/{interview_id}/analysis/latest"],
)

# 注册路由
app.include_router(v1_router, prefix="/api")


# ==================== Global Exception Handlers ====================

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """处理 Pydantic 验证错误"""
    request_id = getattr(request.state, "request_id", "unknown")
    logger = get_logger("app.exception", request_id=request_id)

    errors = []
    for err in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in err.get("loc", [])),
            "message": err.get("msg", "验证失败"),
            "type": err.get("type", ""),
        })

    logger.warning(
        f"Validation error: {len(errors)} field(s) failed",
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "errors": errors,
            "event": "validation_error",
        },
    )
    return JSONResponse(
        status_code=422,
        content={"detail": "请求参数验证失败", "errors": errors},
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常兜底处理器"""
    request_id = getattr(request.state, "request_id", "unknown")
    logger = get_logger("app.exception", request_id=request_id)

    traceback_str = traceback.format_exc()
    logger.error(
        f"Unhandled exception: {exc}",
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "event": "unhandled_exception",
        },
        exc_info=True,
    )

    response_content = {
        "detail": "服务器内部错误，请稍后重试",
        "path": str(request.url.path),
        "method": request.method,
        "request_id": request_id,
    }
    # 开发环境附加堆栈信息
    if settings.DEBUG:
        response_content["traceback"] = traceback_str

    return JSONResponse(
        status_code=500,
        content=response_content,
        headers={"X-Request-ID": request_id},
    )


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
