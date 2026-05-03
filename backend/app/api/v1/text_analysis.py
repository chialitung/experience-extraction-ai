import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, AsyncSessionLocal
from app.core.security import get_current_active_user_optional
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.text_analysis import (
    TextAnalysisCreate, TextAnalysisResponse,
    TextAnalysisListResponse, TextAnalysisExportRequest,
)
from app.services.text_analysis_service import TextAnalysisService

router = APIRouter(prefix="/text-analysis", tags=["text-analysis"])
logger = get_logger("app.api.text_analysis")


async def _run_analysis_in_background(analysis_id: str) -> None:
    """后台异步执行文本分析流程"""
    async with AsyncSessionLocal() as db:
        try:
            service = TextAnalysisService(db)
            await service.run_analysis(analysis_id)
            logger.info(f"Background analysis completed: {analysis_id}")
        except Exception as e:
            logger.error(f"Background analysis failed: {analysis_id}, error: {e}", exc_info=True)


async def get_text_analysis_service(db: AsyncSession = Depends(get_db)) -> TextAnalysisService:
    return TextAnalysisService(db)


def resolve_user_filter(current_user: Optional[User]) -> Optional[str]:
    """解析查询的用户过滤条件。

    - 未登录（演示模式）：返回 None，不过滤
    - 管理员：返回 None，不过滤（可看全部）
    - 普通用户：返回 user_id，只看自己的
    """
    if current_user is None:
        return None
    if current_user.is_superuser:
        return None
    return str(current_user.id)


@router.post("", response_model=TextAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_text_analysis(
    data: TextAnalysisCreate,
    service: TextAnalysisService = Depends(get_text_analysis_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """创建文本分析记录并后台异步执行完整流程（清理→提取→报告）"""
    user_id = str(current_user.id) if current_user else None

    # 创建记录（状态为 pending）
    analysis = await service.create_analysis(data, user_id=user_id)

    # 后台异步执行分析流程，立即返回 pending 状态
    asyncio.create_task(_run_analysis_in_background(str(analysis.id)))
    logger.info(f"Text analysis queued for background processing: {analysis.id}")

    return analysis


@router.get("", response_model=TextAnalysisListResponse)
async def list_text_analyses(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    service: TextAnalysisService = Depends(get_text_analysis_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取文本分析列表"""
    user_filter = resolve_user_filter(current_user)
    items, total = await service.list_analyses(
        user_id=user_filter,
        skip=skip,
        limit=limit,
    )
    return TextAnalysisListResponse(
        items=items,
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        limit=limit,
    )


@router.get("/{analysis_id}", response_model=TextAnalysisResponse)
async def get_text_analysis(
    analysis_id: str,
    service: TextAnalysisService = Depends(get_text_analysis_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """获取单个文本分析详情"""
    analysis = await service.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析记录不存在",
        )

    # 权限检查
    if current_user and not current_user.is_superuser:
        if analysis.user_id and analysis.user_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此分析记录",
            )

    return analysis


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_text_analysis(
    analysis_id: str,
    service: TextAnalysisService = Depends(get_text_analysis_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """删除文本分析记录"""
    # 先获取记录做权限检查
    analysis = await service.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析记录不存在",
        )

    # 权限检查
    if current_user and not current_user.is_superuser:
        if analysis.user_id and analysis.user_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此分析记录",
            )

    success = await service.delete_analysis(analysis_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除失败",
        )

    return None


@router.get("/{analysis_id}/export")
async def export_text_analysis_report(
    analysis_id: str,
    format: str = Query("markdown", pattern="^(markdown|json|docx|pdf)$"),
    service: TextAnalysisService = Depends(get_text_analysis_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """导出分析报告"""
    analysis = await service.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析记录不存在",
        )

    # 权限检查
    if current_user and not current_user.is_superuser:
        if analysis.user_id and analysis.user_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此分析记录",
            )

    if analysis.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"分析尚未完成，当前状态: {analysis.status}",
        )

    try:
        content, filename = service.export_report(analysis, format)
    except Exception as e:
        logger.error(f"Export failed for analysis {analysis_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出失败: {str(e)}",
        )

    from fastapi.responses import Response

    media_types = {
        "markdown": "text/markdown; charset=utf-8",
        "json": "application/json; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }

    return Response(
        content=content,
        media_type=media_types.get(format, "text/plain"),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
