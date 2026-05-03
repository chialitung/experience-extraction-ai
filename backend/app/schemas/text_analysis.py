from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class TextAnalysisCreate(BaseModel):
    theme: str = Field(..., min_length=5, max_length=500, description="萃取主题")
    background: Optional[str] = Field(None, description="业务背景")
    expert_role: Optional[str] = Field(None, description="专家角色")
    raw_text: str = Field(..., min_length=100, description="访谈原始文字记录")


class TextAnalysisResponse(BaseModel):
    id: UUID
    theme: str
    background: Optional[str]
    expert_role: Optional[str]
    raw_text_length: int
    cleaned_messages: List[Dict[str, str]]
    structured_content: Dict[str, Any]
    analysis_report: Dict[str, Any]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TextAnalysisListResponse(BaseModel):
    items: List[TextAnalysisResponse]
    total: int
    page: int
    limit: int


class TextAnalysisExportRequest(BaseModel):
    format: str = Field("markdown", pattern="^(markdown|json|docx|pdf)$")
