from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


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
    
    return {
        "provider": provider,
        "label": label,
        "model": model,
        "base_url": base_url,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
    }
