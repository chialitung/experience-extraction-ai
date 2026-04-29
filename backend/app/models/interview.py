import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON, Enum
from app.core.database import Base


class InterviewState(str, PyEnum):
    EVENT_REVIEW = "event_review"
    FRAMEWORK_BUILD = "framework_build"
    DETAIL_MINING = "detail_mining"
    OBSTACLE_IDENTIFY = "obstacle_identify"
    TOOL_EXTRACT = "tool_extract"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"


class InterviewStatus(str, PyEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


# 保留 OutputFormat 枚举用于前后端契约
class OutputFormat(str, PyEnum):
    SCRIPT_CARD = "script_card"
    CHECKLIST = "checklist"
    FLOWCHART = "flowchart"
    LEARNING_CARD = "learning_card"
    CASE_STUDY = "case_study"
    COMPREHENSIVE = "comprehensive"  # 全套素材包


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    theme = Column(String(500), nullable=False)
    background = Column(Text, nullable=True)
    expert_role = Column(String(200), nullable=True)
    expected_duration = Column(Integer, nullable=True)
    target_output_format = Column(JSON, default=list)  # 改为 JSON 列表，支持多选

    # Blueprint
    blueprint = Column(JSON, default=dict)

    # State
    current_state = Column(Enum(InterviewState), default=InterviewState.EVENT_REVIEW)
    state_history = Column(JSON, default=list)

    # Expert profile
    expert_profile = Column(JSON, default=dict)

    # Value assessment
    value_assessment = Column(JSON, default=dict)

    # Final output
    final_output = Column(JSON, default=dict)

    status = Column(Enum(InterviewStatus), default=InterviewStatus.ACTIVE, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String(36), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False, index=True)  # system, user, assistant
    content = Column(Text, nullable=False)

    # Message classification
    message_type = Column(String(30), nullable=True)  # question, answer, summary, confirmation, blueprint
    question_type = Column(String(30), nullable=True)  # fact, explore, cause, hypothesis, confirm

    # Structured data extracted from this message
    extracted_data = Column(JSON, default=dict)

    # Extra metadata
    extra_metadata = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class StructuredContent(Base):
    __tablename__ = "structured_contents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String(36), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, default=1)

    # Structured data
    steps = Column(JSON, default=list)
    principles = Column(JSON, default=list)
    tools = Column(JSON, default=list)
    risks = Column(JSON, default=list)
    decisions = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
