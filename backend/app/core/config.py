from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Experience Extraction AI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Security
    SECRET_KEY: str = "change-this-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/experience_extraction"
    
    # Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # LLM
    DEFAULT_LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_BASE_URL: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    
    # DeepSeek
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: Optional[str] = "https://api.deepseek.com/v1"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_RETENTION_DAYS: int = 30

    # Baidu Speech Recognition
    BAIDU_SPEECH_APP_ID: Optional[str] = None
    BAIDU_SPEECH_API_KEY: Optional[str] = None
    BAIDU_SPEECH_SECRET_KEY: Optional[str] = None

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
