from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings
from app.core.security import get_current_admin
from app.models.user import User
import os
import re

router = APIRouter()


class ConfigUpdateRequest(BaseModel):
    default_llm_provider: Optional[str] = None
    deepseek_model: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: Optional[str] = None
    baidu_speech_app_id: Optional[str] = None
    baidu_speech_api_key: Optional[str] = None
    baidu_speech_secret_key: Optional[str] = None


@router.get("/config")
async def get_config():
    """获取系统配置（脱敏）"""
    provider = settings.DEFAULT_LLM_PROVIDER

    if provider == "deepseek":
        model = settings.DEEPSEEK_MODEL
        base_url = settings.DEEPSEEK_BASE_URL
        label = "DeepSeek"
    elif provider == "anthropic":
        model = settings.ANTHROPIC_MODEL
        base_url = "https://api.anthropic.com"
        label = "Anthropic"
    else:
        model = settings.OPENAI_MODEL
        base_url = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
        label = "OpenAI Compatible"

    # Mask sensitive values for display
    def mask(s: Optional[str]) -> str:
        if not s:
            return ""
        if len(s) <= 8:
            return "****"
        return s[:4] + "****" + s[-4:]

    return {
        "provider": provider,
        "label": label,
        "model": model,
        "base_url": base_url,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "deepseek_api_key": mask(settings.DEEPSEEK_API_KEY),
        "deepseek_base_url": settings.DEEPSEEK_BASE_URL,
        "baidu_speech_app_id": settings.BAIDU_SPEECH_APP_ID or "",
        "baidu_speech_api_key": mask(settings.BAIDU_SPEECH_API_KEY),
        "baidu_speech_secret_key": mask(settings.BAIDU_SPEECH_SECRET_KEY),
    }


@router.put("/config")
async def update_config(
    request: ConfigUpdateRequest,
    admin: User = Depends(get_current_admin),
):
    """更新系统配置（管理员）

    MVP 实现：将配置写入 backend/.env 文件，重启后生效。
    """
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    if not os.path.exists(env_path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=".env file not found",
        )

    valid_providers = {"openai", "anthropic", "deepseek"}
    if request.default_llm_provider is not None and request.default_llm_provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}",
        )

    # Read existing .env
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Map request fields to env var names
    field_map = {
        "DEFAULT_LLM_PROVIDER": request.default_llm_provider,
        "DEEPSEEK_MODEL": request.deepseek_model,
        "DEEPSEEK_API_KEY": request.deepseek_api_key,
        "DEEPSEEK_BASE_URL": request.deepseek_base_url,
        "BAIDU_SPEECH_APP_ID": request.baidu_speech_app_id,
        "BAIDU_SPEECH_API_KEY": request.baidu_speech_api_key,
        "BAIDU_SPEECH_SECRET_KEY": request.baidu_speech_secret_key,
    }

    updated = []
    for line in lines:
        stripped = line.strip()
        # Skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            updated.append(line)
            continue
        # Match KEY=value or KEY= (with optional comment after)
        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', stripped)
        if match:
            key = match.group(1)
            if key in field_map and field_map[key] is not None:
                updated.append(f"{key}={field_map[key]}\n")
                field_map[key] = None  # Mark as handled
                continue
        updated.append(line)

    # Write back
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(updated)

    return {
        "detail": "配置已保存，请重启后端服务后生效",
        "requires_restart": True,
    }
