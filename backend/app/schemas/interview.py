from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from app.models.interview import InterviewState, InterviewStatus, OutputFormat


# ==================== Interview Schemas ====================

# 可用的成果形式列表
ALL_OUTPUT_FORMATS = [
    OutputFormat.SCRIPT_CARD.value,
    OutputFormat.CHECKLIST.value,
    OutputFormat.FLOWCHART.value,
    OutputFormat.LEARNING_CARD.value,
    OutputFormat.CASE_STUDY.value,
]


class InterviewCreate(BaseModel):
    theme: str = Field(..., min_length=5, max_length=500, description="萃取主题")
    background: Optional[str] = Field(None, description="业务背景")
    expert_role: Optional[str] = Field(None, description="专家角色")
    expected_duration: Optional[int] = Field(30, ge=10, le=120, description="期望时长(分钟)")
    target_output_format: List[str] = Field(default_factory=lambda: [OutputFormat.SCRIPT_CARD.value], description="目标输出格式列表，支持多选；传 ['comprehensive'] 表示全套")


class InterviewUpdate(BaseModel):
    theme: Optional[str] = None
    background: Optional[str] = None
    expert_role: Optional[str] = None
    expected_duration: Optional[int] = None
    target_output_format: Optional[List[str]] = None
    blueprint: Optional[Dict[str, Any]] = None
    current_state: Optional[InterviewState] = None
    expert_profile: Optional[Dict[str, Any]] = None
    value_assessment: Optional[Dict[str, Any]] = None
    final_output: Optional[Dict[str, Any]] = None
    status: Optional[InterviewStatus] = None


class InterviewResponse(BaseModel):
    id: UUID
    theme: str
    background: Optional[str]
    expert_role: Optional[str]
    expected_duration: Optional[int]
    target_output_format: List[str]
    blueprint: Dict[str, Any]
    current_state: InterviewState
    state_history: List[Dict[str, Any]]
    expert_profile: Dict[str, Any]
    value_assessment: Dict[str, Any]
    drift_history: List[Dict[str, Any]]
    final_output: Dict[str, Any]
    status: InterviewStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InterviewListResponse(BaseModel):
    items: List[InterviewResponse]
    total: int
    page: int
    limit: int


# ==================== Blueprint Schemas ====================

class BlueprintStep(BaseModel):
    step: str
    step_name: str
    duration_min: int
    key_questions: List[Dict[str, Any]]
    objectives: List[str]


class ValueAssessment(BaseModel):
    gold: int = Field(..., ge=1, le=10, description="高价值")
    wood: int = Field(..., ge=1, le=10, description="有难度")
    water: int = Field(..., ge=1, le=10, description="常使用")
    fire: int = Field(..., ge=1, le=10, description="急需要")
    earth: int = Field(..., ge=1, le=10, description="覆盖广")
    reasons: Dict[str, str]


class InterviewBlueprint(BaseModel):
    theme: str
    value_assessment: ValueAssessment
    six_steps: List[BlueprintStep]
    target_output: str
    overall_strategy: str


class BlueprintConfirmRequest(BaseModel):
    adjustments: Optional[Dict[str, Any]] = None


# ==================== Message Schemas ====================

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class MessageResponse(BaseModel):
    id: UUID
    interview_id: UUID
    role: str
    content: str
    message_type: Optional[str]
    question_type: Optional[str]
    extracted_data: Dict[str, Any]
    extra_metadata: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Structured Content Schemas ====================

class StepItem(BaseModel):
    order: int
    title: str
    description: str
    details: Optional[str] = None


class PrincipleItem(BaseModel):
    title: str
    description: str
    application_scenario: Optional[str] = None


class ToolItem(BaseModel):
    name: str
    description: str
    usage_method: Optional[str] = None


class RiskItem(BaseModel):
    type: str  # error, difficulty, overlook
    description: str
    prevention: Optional[str] = None


class StructuredContentResponse(BaseModel):
    id: UUID
    interview_id: UUID
    version: int
    steps: List[StepItem]
    principles: List[PrincipleItem]
    tools: List[ToolItem]
    risks: List[RiskItem]
    decisions: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Output Schemas ====================

class OutputExportRequest(BaseModel):
    format: str = Field("markdown", pattern="^(markdown|json|docx|pdf)$")


class OutputResponse(BaseModel):
    interview_id: UUID
    content: str
    format: str
    generated_at: datetime


# ==================== Report Schemas ====================

class ReportGenerateRequest(BaseModel):
    depth: str = Field("standard", pattern="^(brief|standard|deep)$")


class ReportMetadata(BaseModel):
    depth: str
    depth_label: str
    generated_at: str
    word_count: int


class AnalysisReport(BaseModel):
    executive_summary: Optional[str] = None
    case_background: Optional[str] = None
    methodology_framework: Optional[str] = None
    key_steps_analysis: Optional[str] = None
    decision_logic_analysis: Optional[str] = None
    obstacles_and_risks: Optional[str] = None
    tools_and_scripts: Optional[str] = None
    application_guidance: Optional[str] = None
    value_assessment: Optional[str] = None
    lessons_learned: Optional[str] = None
    references: Optional[str] = None


class ReportResponse(BaseModel):
    analysis_report: AnalysisReport
    metadata: ReportMetadata


class ReportExportRequest(BaseModel):
    format: str = Field("markdown", pattern="^(markdown|docx|pdf|json)$")
    depth: str = Field("standard", pattern="^(brief|standard|deep)$")


# ==================== SSE Event Schemas ====================

class SSEEvent(BaseModel):
    event: str
    data: Dict[str, Any]


# ==================== Timer Schemas ====================

class TimerStatusResponse(BaseModel):
    status: str = Field(..., description="计时器状态: running | paused | completed | stopped")
    elapsed_seconds: int = Field(..., ge=0, description="累计已用秒数")


# ==================== Voice Transcription Schemas ====================

class VoiceTranscribeRequest(BaseModel):
    audio_base64: str = Field(..., min_length=1, description="Base64 编码的 WAV(16kHz mono) 音频数据")
    segment_index: int = Field(0, ge=0, description="音频片段序号，用于日志追踪")


class VoiceTranscribeResponse(BaseModel):
    transcription: Optional[str] = Field(None, description="过滤后的专家回答文字，若识别为空则返回 None")
    segment_index: int = Field(..., description="对应的音频片段序号")


# ==================== Round Complete Schemas ====================

class RoundCompleteRequest(BaseModel):
    transcription: Optional[str] = Field(None, description="当前轮次录音转录的原始文字")
    notes: List[str] = Field(default_factory=list, description="用户补充的备注信息列表")


class RoundCompleteResponse(BaseModel):
    refined_answer: str = Field(..., description="AI整理后的专家回答")
    user_message: MessageResponse = Field(..., description="保存的用户消息")
    ai_message: MessageResponse = Field(..., description="AI生成的下一个问题")
