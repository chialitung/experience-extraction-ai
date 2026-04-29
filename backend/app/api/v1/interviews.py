import io
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.security import (
    get_current_active_user, get_current_active_user_optional, decode_access_token
)
from app.core.logging import get_logger
from app.services.interview_service import InterviewService
from app.services.voice_transcription_service import voice_transcription_service
from app.models.interview import Message
from app.models.user import User
from app.schemas.interview import (
    InterviewCreate, InterviewUpdate, InterviewResponse,
    InterviewListResponse, BlueprintConfirmRequest,
    MessageCreate, MessageResponse,
    StructuredContentResponse, OutputResponse, OutputExportRequest,
    ReportGenerateRequest, ReportResponse,
    TimerStatusResponse, VoiceTranscribeRequest, VoiceTranscribeResponse,
    RoundCompleteRequest, RoundCompleteResponse,
)

router = APIRouter(prefix="/interviews", tags=["interviews"])


async def get_interview_service(db: AsyncSession = Depends(get_db)) -> InterviewService:
    return InterviewService(db)


def resolve_user_filter(current_user: Optional[User]) -> Optional[str]:
    """解析访谈查询的用户过滤条件。

    - 未登录（演示模式）：返回 None，不过滤（开放访问）
    - 管理员：返回 None，不过滤（可看全部）
    - 普通用户：返回 user_id，只看自己的
    """
    if current_user is None:
        return None
    if current_user.is_superuser:
        return None
    return str(current_user.id)


# ==================== Interview CRUD ====================

@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
async def create_interview(
    data: InterviewCreate,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """创建新访谈（登录用户关联到当前用户）"""
    user_id = str(current_user.id) if current_user else None
    interview = await service.create_interview(data, user_id=user_id)
    return interview


@router.get("", response_model=InterviewListResponse)
async def list_interviews(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取访谈列表（登录用户只看自己的，未登录看全部）。支持状态过滤和主题搜索。"""
    user_id = resolve_user_filter(current_user)
    interviews, total = await service.list_interviews(
        skip=skip, limit=limit, user_id=user_id, status=status_filter, search=search
    )
    return {
        "items": interviews,
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "limit": limit,
    }


@router.get("/templates")
async def list_templates():
    """获取所有可用的成果模板列表"""
    from app.services.template_service import TemplateService
    return {"templates": TemplateService.list_templates()}


@router.get("/{interview_id}", response_model=InterviewResponse)
async def get_interview(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取访谈详情"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


@router.patch("/{interview_id}", response_model=InterviewResponse)
async def update_interview(
    interview_id: str,
    data: InterviewUpdate,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """更新访谈"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    interview = await service.update_interview(interview_id, data)
    return interview


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """删除访谈（包括进行中的访谈，级联删除消息和结构化内容）"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    success = await service.delete_interview(interview_id)
    if not success:
        raise HTTPException(status_code=404, detail="Interview not found")
    return None


# ==================== Blueprint ====================

@router.post("/{interview_id}/blueprint/generate")
async def generate_blueprint(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """生成访谈蓝图"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    blueprint = await service.generate_blueprint(interview_id)
    return {"blueprint": blueprint}


@router.post("/{interview_id}/blueprint/confirm")
async def confirm_blueprint(
    interview_id: str,
    request: BlueprintConfirmRequest,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """确认蓝图"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # 如果有调整，更新蓝图
    if request.adjustments:
        await service.update_interview(
            interview_id,
            InterviewUpdate(blueprint={**interview.blueprint, **request.adjustments})
        )
    
    return {"success": True, "message": "Blueprint confirmed"}


# ==================== Interview Start ====================

@router.post("/{interview_id}/start", response_model=MessageResponse)
async def start_interview(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """启动访谈，自动生成开场问题"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # 检查是否已有消息，避免重复生成开场问题
    existing_messages = await service.get_messages(interview_id, limit=1)
    if existing_messages:
        return existing_messages[0]

    ai_message = await service.generate_opening_question(interview_id)

    # 自动开始计时
    try:
        await service.start_timer(interview_id)
    except ValueError:
        pass  # 可能已启动，忽略

    return ai_message


# ==================== Messages ====================

@router.post("/{interview_id}/messages", response_model=MessageResponse)
async def send_message(
    interview_id: str,
    data: MessageCreate,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """发送消息并获取AI回复（非流式）"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    response = await service.generate_ai_response(interview_id, data.content)
    
    # 返回最后一条AI消息（按时间降序取最新）
    result = await service.db.execute(
        select(Message)
        .where(Message.interview_id == interview_id)
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest:
        # 手动构建字典返回，避免ORM对象直接给Pydantic带来的序列化风险
        return {
            "id": latest.id,
            "interview_id": latest.interview_id,
            "role": latest.role,
            "content": latest.content,
            "message_type": latest.message_type,
            "question_type": latest.question_type,
            "extracted_data": latest.extracted_data or {},
            "extra_metadata": latest.extra_metadata or {},
            "created_at": latest.created_at,
        }
    
    raise HTTPException(status_code=500, detail="Failed to generate response")


@router.get("/{interview_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    interview_id: str,
    limit: int = 50,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取消息历史"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    messages = await service.get_messages(interview_id, limit=limit)
    return messages


# ==================== Streaming Messages ====================

from fastapi.responses import StreamingResponse


@router.post("/{interview_id}/messages/stream")
async def send_message_stream(
    interview_id: str,
    data: MessageCreate,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """发送消息并获取AI流式回复"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    async def event_generator():
        async for chunk in service.generate_ai_response_stream(interview_id, data.content):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# ==================== Structured Content ====================

@router.get("/{interview_id}/structured-content")
async def get_structured_content(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取实时结构化萃取内容"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    content = await service.get_structured_content_response(interview_id)
    return content


# ==================== Output ====================

@router.post("/{interview_id}/complete")
async def complete_interview(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """完成访谈，生成最终成果"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    final_output = await service.complete_interview(interview_id)
    return {"output": final_output}


@router.get("/{interview_id}/output")
async def get_output(
    interview_id: str,
    format: str = "json",
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取成果"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    if not interview.final_output:
        raise HTTPException(status_code=400, detail="Interview not completed yet")
    
    return {
        "interview_id": interview_id,
        "content": interview.final_output,
        "format": format,
        "generated_at": interview.updated_at,
    }


# ==================== Expert Profile & Analysis ====================

@router.get("/{interview_id}/expert-profile")
async def get_expert_profile(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取专家画像（沟通风格分析结果）"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    profile = interview.expert_profile or {}
    return {
        "interview_id": interview_id,
        "expert_profile": profile,
        "is_identified": bool(profile.get("profile_type")),
    }


@router.get("/{interview_id}/analysis/latest")
async def get_latest_analysis(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取最新内容分析结果（回答颗粒度、偏离检测、信息缺口）"""
    from sqlalchemy import desc
    
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # 获取最新的AI消息中的分析元数据
    result = await service.db.execute(
        select(Message)
        .where(Message.interview_id == interview_id)
        .where(Message.role == "assistant")
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    latest_ai_msg = result.scalar_one_or_none()
    
    analysis = {}
    if latest_ai_msg and latest_ai_msg.extra_metadata:
        analysis = latest_ai_msg.extra_metadata.get("content_analysis", {})
    
    return {
        "interview_id": interview_id,
        "analysis": analysis,
        "has_analysis": bool(analysis),
    }


@router.post("/{interview_id}/risks/mark")
async def mark_risks(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """触发风险标引（对最新用户回答进行规则引擎风险识别）"""
    from app.services.risk_marker import risk_marker
    from sqlalchemy import desc
    
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # 获取最新用户回答
    result = await service.db.execute(
        select(Message)
        .where(Message.interview_id == interview_id)
        .where(Message.role == "user")
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    latest_user_msg = result.scalar_one_or_none()
    
    if not latest_user_msg:
        raise HTTPException(status_code=400, detail="No user message found")
    
    risk_result = risk_marker.mark_risks(latest_user_msg.content)
    return risk_marker.to_dict(risk_result)


# ==================== Templates & Export ====================

@router.get("/{interview_id}/render")
async def render_template(
    interview_id: str,
    template: str = "script_card",
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """使用指定模板渲染访谈成果"""
    from app.services.template_service import TemplateService
    
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # 构建渲染数据
    structured = await service.get_structured_content_response(interview_id)
    render_data = {
        "theme": interview.theme,
        "background": interview.background or "",
        **structured,
    }
    
    rendered = TemplateService.render(template, render_data)
    return {
        "interview_id": interview_id,
        "template": template,
        "content": rendered,
    }


@router.get("/{interview_id}/export")
async def export_output(
    interview_id: str,
    format: str = "markdown",
    template: str = "script_card",
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """导出访谈成果为指定格式"""
    from fastapi.responses import StreamingResponse
    from app.services.template_service import TemplateService
    from app.services.export_service import ExportService
    
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # 获取结构化内容并渲染
    structured = await service.get_structured_content_response(interview_id)
    render_data = {
        "theme": interview.theme,
        "background": interview.background or "",
        **structured,
    }
    rendered = TemplateService.render(template, render_data)
    
    # 构建文件名基础（强制 ASCII，彻底避免中文编码问题）
    safe_theme = "".join(c for c in (interview.theme or "") if c.isascii() and (c.isalnum() or c in (' ', '-', '_'))).strip()[:30]
    filename_base = f"{safe_theme or 'interview'}_{interview_id[:8]}"
    
    # 根据格式导出
    media_types = {
        "markdown": "text/markdown; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "text/html; charset=utf-8",
        "json": "application/json; charset=utf-8",
    }
    
    if format == "markdown":
        data, filename = ExportService.export_markdown(rendered, filename_base)
    elif format == "docx":
        data, filename = ExportService.export_docx(rendered, interview.theme, filename_base)
    elif format == "pdf":
        data, filename = ExportService.export_pdf(rendered, interview.theme, filename_base)
    elif format == "json":
        data, filename = ExportService.export_json(render_data, filename_base)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
    
    # HTTP headers 必须用 latin-1 编码，中文文件名需使用 RFC 5987 格式
    from urllib.parse import quote
    safe_filename = quote(filename, safe='')
    content_disposition = f"attachment; filename*=UTF-8''{safe_filename}"

    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_types.get(format, "application/octet-stream"),
        headers={"Content-Disposition": content_disposition},
    )


# ==================== Analysis Report ====================

@router.post("/{interview_id}/report")
async def generate_report(
    interview_id: str,
    request: ReportGenerateRequest,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """生成经验分析报告（支持任意时间重新生成，可指定深度）"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    report = await service.generate_report(interview_id, depth=request.depth)
    return report


@router.get("/{interview_id}/report")
async def get_report(
    interview_id: str,
    depth: Optional[str] = None,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取已生成的经验分析报告（支持按深度获取）"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    report = await service.get_report(interview_id, depth=depth)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found. Please generate it first.")

    return report


@router.get("/{interview_id}/report/export")
async def export_report(
    interview_id: str,
    format: str = "markdown",
    depth: str = "standard",
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """导出经验分析报告为指定格式"""
    from fastapi.responses import StreamingResponse
    from app.services.report_service import report_service
    from app.services.export_service import ExportService

    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # 获取或生成报告
    report = await service.get_report(interview_id)
    if not report or report.get("metadata", {}).get("depth") != depth:
        # 如果报告不存在或深度不匹配，重新生成
        report = await service.generate_report(interview_id, depth=depth)

    # 转换为Markdown
    markdown_content = report_service.report_to_markdown(report, interview.theme)

    # 构建文件名（强制 ASCII，彻底避免中文编码问题）
    safe_theme = "".join(c for c in (interview.theme or "") if c.isascii() and (c.isalnum() or c in (' ', '-', '_'))).strip()[:30]
    filename_base = f"{safe_theme or 'interview'}_报告_{depth}"

    media_types = {
        "markdown": "text/markdown; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "text/html; charset=utf-8",
        "json": "application/json; charset=utf-8",
    }

    if format == "markdown":
        data, filename = ExportService.export_markdown(markdown_content, filename_base)
    elif format == "docx":
        data, filename = ExportService.export_docx(markdown_content, interview.theme, filename_base)
    elif format == "pdf":
        data, filename = ExportService.export_pdf(markdown_content, interview.theme, filename_base)
    elif format == "json":
        data, filename = ExportService.export_json(report, filename_base)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    # HTTP headers 必须用 latin-1 编码，中文文件名需使用 RFC 5987 格式
    from urllib.parse import quote
    safe_filename = quote(filename, safe='')
    content_disposition = f"attachment; filename*=UTF-8''{safe_filename}"

    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_types.get(format, "application/octet-stream"),
        headers={"Content-Disposition": content_disposition},
    )


# ==================== Timer ====================

@router.post("/{interview_id}/timer/start", response_model=TimerStatusResponse)
async def start_timer(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """开始计时"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    try:
        result = await service.start_timer(interview_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{interview_id}/timer/pause", response_model=TimerStatusResponse)
async def pause_timer(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """暂停计时"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    try:
        result = await service.pause_timer(interview_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{interview_id}/timer/resume", response_model=TimerStatusResponse)
async def resume_timer(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """恢复计时"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    try:
        result = await service.resume_timer(interview_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{interview_id}/timer/status", response_model=TimerStatusResponse)
async def get_timer_status(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取计时状态"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    result = await service.get_timer_status(interview_id)
    return result


# ==================== Voice Transcription ====================

@router.post("/{interview_id}/voice/transcribe", response_model=VoiceTranscribeResponse)
async def transcribe_voice(
    interview_id: str,
    request: VoiceTranscribeRequest,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """
    [DEPRECATED] 接收音频片段，返回语音识别 + LLM 过滤后的专家回答文字

    ⚠️ 已废弃：请使用 WebSocket 实时语音识别 /ws/interviews/{interview_id}/transcribe
    此 HTTP 轮询接口保留用于兼容，新功能请迁移至 WebSocket 流式识别。

    转录文字不会自动保存为消息，由前端放入输入框供专家编辑后手动发送
    """
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # 获取最近 3 条 AI 提问用于过滤
    messages = await service.get_messages(interview_id, limit=20)
    recent_questions = []
    for msg in reversed(messages):
        if msg.role == "assistant" and msg.content:
            recent_questions.append(msg.content[:300])
        if len(recent_questions) >= 3:
            break

    transcription = await voice_transcription_service.transcribe_segment(
        interview_id=interview_id,
        audio_base64=request.audio_base64,
        segment_index=request.segment_index,
        recent_questions=recent_questions,
    )

    return {
        "transcription": transcription,
        "segment_index": request.segment_index,
    }


# ==================== Round Complete (Voice Mode) ====================

@router.post("/{interview_id}/round/complete")
async def complete_round(
    interview_id: str,
    request: RoundCompleteRequest,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """
    完成当前录音轮次：
    1. AI 整理转录内容（删除 AI 提问、纠正错别字、去语气词）
    2. 拼接用户备注
    3. 保存为用户消息
    4. 生成 AI 下一个问题
    """
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    result = await service.complete_round(
        interview_id=interview_id,
        transcription=request.transcription,
        notes=request.notes,
    )

    # 手动构建字典返回，避免 ORM 对象直接给 Pydantic 带来的序列化风险
    def msg_to_dict(msg):
        if not msg:
            return None
        return {
            "id": msg.id,
            "interview_id": msg.interview_id,
            "role": msg.role,
            "content": msg.content,
            "message_type": msg.message_type,
            "question_type": msg.question_type,
            "extracted_data": msg.extracted_data or {},
            "extra_metadata": msg.extra_metadata or {},
            "created_at": msg.created_at,
        }

    return {
        "refined_answer": result["refined_answer"],
        "user_message": msg_to_dict(result["user_message"]),
        "ai_message": msg_to_dict(result["ai_message"]),
    }


# ==================== Realtime Transcription (WebSocket) ====================

@router.websocket("/{interview_id}/transcribe")
async def realtime_transcribe(
    websocket: WebSocket,
    interview_id: str,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """WebSocket 实时语音识别代理（前端 PCM 流 → 百度实时语音识别）

    连接建立后：
    1. 前端发送二进制 PCM 音频数据（16kHz, 16bit, 单声道, 160ms/帧）
    2. 后端实时转发至百度 WebSocket
    3. 后端将百度返回的 MID_TEXT / FIN_TEXT 实时推送回前端
    4. 前端发送 {"action":"stop"} 或断开连接时结束

    认证方式：通过 URL query parameter `?token=<JWT>` 传递
    """
    ws_logger = get_logger("app.ws.transcribe")

    ws_logger.info(
        "WebSocket 实时转录请求到达",
        extra={
            "interview_id": interview_id,
            "has_token": bool(token),
            "event": "ws_transcribe_request",
        },
    )

    # 手动解析 JWT Token（WebSocket 不支持标准 HTTP Authorization header）
    current_user: Optional[User] = None
    if token:
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub")
            if user_id:
                result = await db.execute(select(User).where(User.id == user_id))
                current_user = result.scalar_one_or_none()

    # 访谈权限校验
    user_id = resolve_user_filter(current_user)
    interview_service = InterviewService(db)
    interview = await interview_service.get_interview(interview_id, user_id=user_id)
    if not interview:
        ws_logger.warning(
            "WebSocket 鉴权失败：访谈不存在或无权限",
            extra={"interview_id": interview_id, "user_id": user_id},
        )
        await websocket.close(code=4004, reason="Interview not found")
        return

    await websocket.accept()
    ws_logger.info(
        "WebSocket 连接已接受",
        extra={"interview_id": interview_id, "event": "ws_transcribe_accepted"},
    )

    from app.services.baidu_realtime_asr_service import BaiduRealtimeASRClient

    baidu_client = BaiduRealtimeASRClient(cuid=str(interview_id))

    async def on_baidu_result(result_type: str, text: str) -> None:
        try:
            await websocket.send_json({"type": result_type, "text": text})
            ws_logger.info(
                "识别结果已转发前端",
                extra={
                    "interview_id": interview_id,
                    "result_type": result_type,
                    "text_preview": text[:50] if text else "",
                },
            )
        except Exception as e:
            ws_logger.error(f"转发识别结果到前端失败: {e}")

    baidu_client.on_result(on_baidu_result)

    connected = await baidu_client.connect()
    if not connected:
        ws_logger.error(
            "百度实时语音识别连接失败",
            extra={"interview_id": interview_id, "event": "baidu_connect_failed"},
        )
        await websocket.send_json(
            {"type": "ERROR", "text": "无法连接到语音识别服务，请检查百度语音配置"}
        )
        await websocket.close(code=1011)
        return

    ws_logger.info(
        "百度实时语音识别已就绪，开始接收音频",
        extra={"interview_id": interview_id, "event": "baidu_ready"},
    )

    try:
        audio_frame_count = 0
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                ws_logger.info(
                    "前端 WebSocket 断开",
                    extra={"interview_id": interview_id, "audio_frames_received": audio_frame_count},
                )
                break

            if message.get("type") == "websocket.receive":
                if "text" in message:
                    # 控制消息（如 {"action":"stop"}）
                    try:
                        cmd = json.loads(message["text"])
                        if cmd.get("action") == "stop":
                            ws_logger.info(
                                "收到前端停止指令",
                                extra={"interview_id": interview_id},
                            )
                            break
                    except json.JSONDecodeError:
                        pass

                elif "bytes" in message:
                    # 音频二进制数据
                    pcm_data = message["bytes"]
                    # 计算音频帧统计信息，用于诊断音频数据是否有效
                    if len(pcm_data) >= 2:
                        import struct
                        samples = struct.unpack(f"<{len(pcm_data)//2}h", pcm_data[:len(pcm_data)//2*2])
                        avg_level = sum(abs(s) for s in samples) / len(samples)
                        max_level = max(abs(s) for s in samples)
                    else:
                        avg_level = 0
                        max_level = 0
                    await baidu_client.send_audio(pcm_data)
                    audio_frame_count += 1
                    if audio_frame_count <= 5 or audio_frame_count % 50 == 0:
                        ws_logger.info(
                            "收到并转发音频帧",
                            extra={
                                "interview_id": interview_id,
                                "frame_count": audio_frame_count,
                                "frame_size": len(pcm_data),
                                "avg_level": round(avg_level, 1),
                                "max_level": max_level,
                            },
                        )

    except WebSocketDisconnect:
        ws_logger.info(
            f"前端 WebSocket 断开: interview_id={interview_id}",
            extra={"audio_frames_received": audio_frame_count},
        )
    except Exception as e:
        ws_logger.error(
            f"WebSocket 转录异常: {e}",
            extra={"interview_id": interview_id, "event": "ws_transcribe_error"},
            exc_info=True,
        )
    finally:
        ws_logger.info(
            "WebSocket 转录会话结束",
            extra={
                "interview_id": interview_id,
                "audio_frames_received": audio_frame_count,
                "event": "ws_transcribe_end",
            },
        )
        await baidu_client.close()
        try:
            await websocket.close()
        except Exception:
            pass
