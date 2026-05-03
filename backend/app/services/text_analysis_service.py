import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from uuid import uuid4

from app.models.text_analysis import TextAnalysis
from app.schemas.text_analysis import TextAnalysisCreate
from app.services.text_cleanup_service import text_cleanup_service
from app.services.llm_service import llm_service
from app.services.report_service import report_service
from app.services.prompt_manager import prompt_manager
from app.core.logging import get_logger


logger = get_logger("app.text_analysis")


class TextAnalysisService:
    """已有访谈文本智能分析服务

    协调完整分析流程：文本清理 -> 结构化提取 -> 报告生成
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_analysis(self, data: TextAnalysisCreate, user_id: Optional[str] = None) -> TextAnalysis:
        """创建分析记录"""
        analysis = TextAnalysis(
            id=str(uuid4()),
            user_id=user_id,
            theme=data.theme,
            background=data.background,
            expert_role=data.expert_role,
            raw_text=data.raw_text,
            raw_text_length=len(data.raw_text),
            status="pending",
        )
        self.db.add(analysis)
        await self.db.commit()
        await self.db.refresh(analysis)
        logger.info(f"Text analysis created: {analysis.id}, theme={analysis.theme}")
        return analysis

    async def run_analysis(self, analysis_id: str) -> TextAnalysis:
        """执行完整分析流程（同步执行）

        流程：pending -> cleaning -> extracting -> reporting -> completed/failed
        """
        result = await self.db.execute(select(TextAnalysis).where(TextAnalysis.id == analysis_id))
        analysis = result.scalar_one_or_none()
        if not analysis:
            raise ValueError(f"TextAnalysis not found: {analysis_id}")

        try:
            # Step 1: 文本清理
            analysis.status = "cleaning"
            await self.db.commit()

            cleaned_messages = await text_cleanup_service.cleanup(analysis.raw_text)
            analysis.cleaned_messages = cleaned_messages
            logger.info(f"Analysis {analysis_id}: cleanup completed, {len(cleaned_messages)} messages")

            if not cleaned_messages:
                analysis.status = "failed"
                analysis.error_message = "文本清理后未得到有效内容，请检查输入文本是否为访谈记录"
                await self.db.commit()
                return analysis

            # Step 2: 结构化提取
            analysis.status = "extracting"
            await self.db.commit()

            structured_content = await self._extract_structured_content(
                theme=analysis.theme,
                background=analysis.background,
                expert_role=analysis.expert_role,
                messages=cleaned_messages,
            )
            analysis.structured_content = structured_content
            logger.info(f"Analysis {analysis_id}: extraction completed, "
                       f"steps={len(structured_content.get('steps', []))}, "
                       f"principles={len(structured_content.get('principles', []))}, "
                       f"tools={len(structured_content.get('tools', []))}, "
                       f"risks={len(structured_content.get('risks', []))}")

            # Step 3: 报告生成（专家版）
            analysis.status = "reporting"
            await self.db.commit()

            report_data = await report_service.generate_report(
                theme=analysis.theme,
                background=analysis.background or "",
                expert_role=analysis.expert_role or "",
                messages=cleaned_messages,
                structured_content=structured_content,
                final_output={},
                blueprint={},
                value_assessment={},
                expert_profile={},
                depth="expert",
            )
            analysis.analysis_report = report_data
            logger.info(f"Analysis {analysis_id}: report generated, "
                       f"depth=expert, words={report_data.get('metadata', {}).get('word_count', 0)}")

            # 完成
            analysis.status = "completed"
            await self.db.commit()
            await self.db.refresh(analysis)
            return analysis

        except Exception as e:
            logger.error(f"Analysis {analysis_id} failed: {e}", exc_info=True)
            analysis.status = "failed"
            analysis.error_message = str(e)[:500]
            await self.db.commit()
            return analysis

    async def _extract_structured_content(
        self,
        theme: str,
        background: Optional[str],
        expert_role: Optional[str],
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """从清理后的消息中提取结构化内容"""
        prompt = prompt_manager.render(
            "tasks/text_structured_extraction.md",
            {
                "theme": theme,
                "background": background,
                "expert_role": expert_role,
                "messages": messages,
            },
        )

        system_prompt = (
            "你是一位资深的企业知识管理顾问和经验萃取专家。"
            "你的任务是从访谈记录中系统性地提取结构化经验知识。"
            "严格按JSON格式输出，不要输出任何额外文字。"
        )

        response = await llm_service.generate_json(
            system_prompt,
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=8000,
        )

        # 验证并规范化返回结构
        result = {
            "steps": self._normalize_list(response.get("steps", [])),
            "principles": self._normalize_list(response.get("principles", [])),
            "tools": self._normalize_list(response.get("tools", [])),
            "risks": self._normalize_list(response.get("risks", [])),
            "decisions": self._normalize_list(response.get("decisions", [])),
            "scenario_variables": self._normalize_list(response.get("scenario_variables", [])),
            "success_factors": self._normalize_list(response.get("success_factors", [])),
            "root_cause_chains": self._normalize_list(response.get("root_cause_chains", [])),
        }

        return result

    def _normalize_list(self, data: Any) -> List[Dict[str, Any]]:
        """确保返回的是列表格式"""
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    async def get_analysis(self, analysis_id: str) -> Optional[TextAnalysis]:
        """获取分析记录"""
        result = await self.db.execute(select(TextAnalysis).where(TextAnalysis.id == analysis_id))
        return result.scalar_one_or_none()

    async def list_analyses(
        self,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[TextAnalysis], int]:
        """列表查询"""
        query = select(TextAnalysis)
        count_query = select(func.count(TextAnalysis.id))

        if user_id:
            query = query.where(TextAnalysis.user_id == user_id)
            count_query = count_query.where(TextAnalysis.user_id == user_id)

        query = query.order_by(desc(TextAnalysis.created_at)).offset(skip).limit(limit)

        result = await self.db.execute(query)
        items = result.scalars().all()

        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        return list(items), total

    async def delete_analysis(self, analysis_id: str) -> bool:
        """删除分析记录"""
        result = await self.db.execute(select(TextAnalysis).where(TextAnalysis.id == analysis_id))
        analysis = result.scalar_one_or_none()
        if not analysis:
            return False

        await self.db.delete(analysis)
        await self.db.commit()
        logger.info(f"Text analysis deleted: {analysis_id}")
        return True

    def export_report(self, analysis: TextAnalysis, format_type: str) -> tuple[str, str]:
        """导出报告

        Returns:
            (content, filename)
        """
        theme = analysis.theme
        report_data = analysis.analysis_report

        if format_type == "markdown":
            content = report_service.report_to_markdown(report_data, theme)
            filename = f"{theme}_专家版分析报告.md"
            return content, filename

        elif format_type == "json":
            content = json.dumps(report_data, ensure_ascii=False, indent=2)
            filename = f"{theme}_专家版分析报告.json"
            return content, filename

        elif format_type in ("docx", "pdf"):
            # 先生成markdown，再用ExportService转换
            md_content = report_service.report_to_markdown(report_data, theme)
            from app.services.export_service import ExportService
            filename_base = f"{theme}_专家版分析报告"
            if format_type == "docx":
                content, filename = ExportService.export_docx(md_content, theme, filename_base)
            else:
                content, filename = ExportService.export_pdf(md_content, theme, filename_base)
            return content, filename

        else:
            raise ValueError(f"Unsupported export format: {format_type}")
