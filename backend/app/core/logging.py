"""统一日志配置模块。

提供结构化 JSON 日志输出，支持 console + file 双通道，
按天轮转，自动清理过期日志（默认保留 30 天）。
"""

import json
import logging
import logging.handlers
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器。"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 附加字段 - 收集所有非标准 LogRecord 属性
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "process", "processName", "exc_info", "exc_text",
            "stack_info", "message", "asctime", "getMessage", "exc_info", "exc_text",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = value

        # 异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class ExtraAdapter(logging.LoggerAdapter):
    """支持额外字段的日志适配器。"""

    def process(self, msg: str, kwargs: Any) -> tuple:
        extra = kwargs.get("extra", {})
        if self.extra:
            extra = {**self.extra, **extra}
        kwargs["extra"] = extra
        return msg, kwargs


def _get_log_level() -> int:
    """从配置解析日志级别。"""
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(settings.LOG_LEVEL.upper(), logging.INFO)


def _ensure_log_dir() -> str:
    """确保日志目录存在。"""
    log_dir = settings.LOG_DIR
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def setup_logging() -> None:
    """初始化全局日志配置。"""
    root_logger = logging.getLogger()
    root_logger.setLevel(_get_log_level())

    # 清除已有处理器，避免重复
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 控制台输出（开发环境可读格式，生产环境 JSON）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(_get_log_level())
    if settings.DEBUG:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    else:
        console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)

    # 文件输出（JSON 格式，按天轮转）
    log_dir = _ensure_log_dir()
    app_log_path = os.path.join(log_dir, "app.log")
    file_handler = logging.handlers.TimedRotatingFileHandler(
        app_log_path,
        when="midnight",
        interval=1,
        backupCount=settings.LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    file_handler.setLevel(_get_log_level())
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # 错误日志单独文件（ERROR 及以上）
    error_log_path = os.path.join(log_dir, "error.log")
    error_handler = logging.handlers.TimedRotatingFileHandler(
        error_log_path,
        when="midnight",
        interval=1,
        backupCount=settings.LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)

    # 降低第三方库日志级别，减少噪音
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str, request_id: Optional[str] = None) -> ExtraAdapter:
    """获取带 request_id 上下文的日志适配器。"""
    logger = logging.getLogger(name)
    extra: Dict[str, Any] = {}
    if request_id:
        extra["request_id"] = request_id
    return ExtraAdapter(logger, extra)


def generate_request_id() -> str:
    """生成唯一请求 ID。"""
    return f"req-{uuid.uuid4().hex[:8]}"
