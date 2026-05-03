import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON
from app.core.database import Base


class TextAnalysis(Base):
    """已有访谈文本智能分析记录"""
    __tablename__ = "text_analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    # 基本信息（用户输入）
    theme = Column(String(500), nullable=False)
    background = Column(Text, nullable=True)
    expert_role = Column(String(200), nullable=True)

    # 原始文本
    raw_text = Column(Text, nullable=False)
    raw_text_length = Column(Integer, default=0)

    # LLM清理后的有效消息
    # 格式: [{"role": "interviewer", "content": "..."}, {"role": "expert", "content": "..."}]
    cleaned_messages = Column(JSON, default=list)

    # 结构化萃取内容
    structured_content = Column(JSON, default=dict)

    # 专家版分析报告
    analysis_report = Column(JSON, default=dict)

    # 处理状态
    status = Column(String(30), default="pending")
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
