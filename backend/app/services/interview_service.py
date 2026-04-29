import asyncio
import json
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.interview import Interview, Message, StructuredContent, InterviewState, InterviewStatus, OutputFormat
from app.schemas.interview import InterviewCreate, InterviewUpdate, MessageCreate, ALL_OUTPUT_FORMATS
from app.services.llm_service import llm_service
from app.services.prompt_manager import prompt_manager
from app.services.expert_profiler import expert_profiler, ExpertProfile
from app.services.content_analyzer import content_analyzer, AnswerAnalysis
from app.services.risk_marker import risk_marker, RiskMarkerResult
from app.services.report_service import report_service
from app.core.cache import structured_content_cache, interview_cache
from app.core.logging import get_logger
from app.core.config import settings


class InterviewService:
    """访谈核心服务：管理访谈生命周期、状态机、AI对话"""
    
    # 六步流程定义
    STATE_FLOW = [
        InterviewState.EVENT_REVIEW,
        InterviewState.FRAMEWORK_BUILD,
        InterviewState.DETAIL_MINING,
        InterviewState.OBSTACLE_IDENTIFY,
        InterviewState.TOOL_EXTRACT,
        InterviewState.CONFIRMATION,
        InterviewState.COMPLETED,
    ]
    
    # 每个访谈步骤最多允许的AI提问轮数（含开场问题）
    # 注意：这是第三层兜底（轮数兜底），在LLM建议+字数兜底之后触发
    # 2026-04-25 修复：从5收紧到3，防止60分钟访谈 stuck 在第一阶段
    MAX_TURNS_PER_STATE = 3

    # 阶段差异化字数时长比例配置（占访谈总时长的比例）
    # 用于第二层兜底：当某阶段用户回答字数超过该阶段字数上限时强制推进
    STATE_WORD_DURATION_RATIOS = {
        "event_review": 0.25,      # 复盘事件：案例背景+冲突+行动+结果，信息量大
        "framework_build": 0.20,   # 建构框架：提炼方法论框架
        "detail_mining": 0.25,     # 挖掘细节：深挖每个步骤的具体动作、话术、工具
        "obstacle_identify": 0.15, # 识别障碍：常见误区和困难点
        "tool_extract": 0.10,      # 提炼工具：转化为可直接使用的工具
        "confirmation": 0.05,      # 复述确认：信息量最小
    }

    # 说话速度参考值（字/分钟），用于字数↔时长换算
    WORDS_PER_MINUTE = 200

    # 状态名标准化映射（处理LLM输出的中英文变体、标点、空格等）
    # 2026-04-25 修复：移除单字映射，防止"框架""细节"等单字被错误匹配导致状态误判
    _STATE_NORMALIZATION = {
        "event_review": "event_review",
        "复盘事件": "event_review",
        "framework_build": "framework_build",
        "建构框架": "framework_build",
        "detail_mining": "detail_mining",
        "挖掘细节": "detail_mining",
        "obstacle_identify": "obstacle_identify",
        "识别障碍": "obstacle_identify",
        "tool_extract": "tool_extract",
        "提炼工具": "tool_extract",
        "confirmation": "confirmation",
        "复述确认": "confirmation",
        "completed": "completed",
        "已完成": "completed",
    }

    def _normalize_state_name(self, name: Optional[str]) -> str:
        """标准化状态名：去除空格、标点、统一大小写，支持前缀匹配"""
        if not name:
            return ""
        cleaned = name.strip().lower().replace(" ", "").replace("·", "").replace("•", "").replace("：", ":").replace("　", "")
        cleaned = cleaned.rstrip("。.,;!?！？")
        # 精确匹配
        if cleaned in self._STATE_NORMALIZATION:
            return self._STATE_NORMALIZATION[cleaned]
        # 前缀匹配：处理 LLM 输出的带描述状态名，如"复盘事件获取成功案例背景"
        for key, value in self._STATE_NORMALIZATION.items():
            if cleaned.startswith(key):
                return value
        return cleaned

    def _calculate_stage_limit(self, interview: Interview) -> int:
        """根据访谈总时长计算每阶段最大轮数"""
        duration = interview.expected_duration or 30
        # 经验公式：每轮问答约消耗 2-3 分钟
        avg_minutes_per_turn = 2.5
        max_total_turns = int(duration / avg_minutes_per_turn)
        # 保证至少 6阶段×2轮=12轮，最多 6阶段×6轮=36轮
        available_turns = max(12, min(36, max_total_turns))
        calculated = max(2, min(6, int(available_turns / 6)))
        # 硬兜底：不超过 MAX_TURNS_PER_STATE
        return min(calculated, self.MAX_TURNS_PER_STATE)

    def _calculate_time_budget(self, interview: Interview, current_turns: int, current_state: str = "", stage_word_count: int = 0) -> Dict[str, Any]:
        """计算当前阶段的时间预算信息（支持阶段差异化字数预算）"""
        duration = interview.expected_duration or 30
        wpm_low, wpm_high = 150, 250
        wpm_avg = self.WORDS_PER_MINUTE
        total_word_budget = duration * wpm_avg

        # 阶段差异化字数预算（不再统一除以6）
        ratio = self.STATE_WORD_DURATION_RATIOS.get(current_state, 1 / 6)
        stage_word_budget = int(total_word_budget * ratio)

        max_turns = self._calculate_stage_limit(interview)
        remaining_turns = max(0, max_turns - current_turns)

        # 字数预算相关
        stage_word_limit = stage_word_budget
        remaining_words = max(0, stage_word_limit - stage_word_count)

        return {
            "total_duration_min": duration,
            "words_per_minute_range": f"{wpm_low}-{wpm_high}",
            "total_word_budget": total_word_budget,
            "stage_word_budget": stage_word_budget,  # 当前阶段差异化字数预算
            "max_turns_per_stage": max_turns,
            "current_turns": current_turns,
            "remaining_turns": remaining_turns,
            "current_state": current_state,
            "current_stage_word_count": stage_word_count,  # 当前阶段已用字数
            "stage_word_limit": stage_word_limit,          # 当前阶段字数上限
            "remaining_words": remaining_words,            # 当前阶段剩余字数
        }

    async def _get_stage_word_count(self, interview_id: UUID) -> int:
        """统计当前阶段用户回答（role == 'user'）的总字数"""
        cache_key = f"stage_word_count:{interview_id}"
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        interview = await self.get_interview(interview_id)
        if not interview:
            return 0

        messages = await self.get_messages(interview_id, limit=100)
        current_state = interview.current_state.value

        # 获取当前阶段起始时间（从 state_history 最后一条）
        history = interview.state_history or []
        last_transition_time = None
        if history:
            last_transition_time = history[-1].get("transitioned_at") or history[-1].get("timestamp")

        total = 0
        checked = 0
        for msg in messages:
            # 只统计用户回答
            if msg.role != "user":
                continue
            checked += 1

            # 方法1：使用 state_history 转换时间分界
            if last_transition_time and msg.created_at:
                try:
                    from datetime import datetime
                    ts = last_transition_time
                    if "T" not in ts and " " in ts:
                        ts = ts.replace(" ", "T", 1)
                    transition_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if msg.created_at.replace(tzinfo=None) <= transition_dt.replace(tzinfo=None):
                        # 消息在转换时间之前，属于旧阶段，跳过
                        continue
                except (ValueError, TypeError, AttributeError):
                    pass  # 解析失败，进入方法2

            # 方法2：使用 metadata 中的 current_step 匹配（鲁棒版本）
            state_meta = msg.extra_metadata.get("state_assessment", {}) if msg.extra_metadata else {}
            msg_state = state_meta.get("current_step") or current_state
            normalized_msg_state = self._normalize_state_name(msg_state)
            normalized_current_state = self._normalize_state_name(current_state)

            if normalized_msg_state == normalized_current_state:
                if msg.content:
                    total += len(msg.content)
            else:
                # 状态不匹配，属于旧阶段
                self.logger.debug(
                    f"Word count skip msg {msg.id}: state mismatch",
                    extra={
                        "interview_id": str(interview_id),
                        "msg_id": str(msg.id),
                        "msg_state": msg_state,
                        "current_state": current_state,
                    },
                )

        self.logger.info(
            f"Counted {total} chars in current state for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "current_state": current_state,
                "user_messages_checked": checked,
                "stage_word_count": total,
                "event": "stage_word_count_complete",
            },
        )
        self._query_cache[cache_key] = total
        return total

    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("app.interview")
        self._query_cache: Dict[str, Any] = {}

    def _resolve_output_formats(self, formats: List[str]) -> List[str]:
        """解析目标成果形式列表，处理 comprehensive 快捷选项"""
        if not formats:
            return [OutputFormat.SCRIPT_CARD.value]
        resolved = set()
        for f in formats:
            if f == OutputFormat.COMPREHENSIVE.value:
                resolved.update(ALL_OUTPUT_FORMATS)
            elif f in ALL_OUTPUT_FORMATS:
                resolved.add(f)
        return list(resolved) if resolved else [OutputFormat.SCRIPT_CARD.value]

    # ==================== CRUD Operations ====================

    async def create_interview(self, data: InterviewCreate, user_id: Optional[str] = None) -> Interview:
        """创建新访谈"""
        resolved_formats = self._resolve_output_formats(data.target_output_format)
        interview = Interview(
            user_id=user_id,
            theme=data.theme,
            background=data.background,
            expert_role=data.expert_role,
            expected_duration=data.expected_duration,
            target_output_format=resolved_formats,
        )
        self.db.add(interview)
        await self.db.flush()
        await self.db.refresh(interview)
        self.logger.info(
            f"Interview created: {interview.id}",
            extra={
                "interview_id": str(interview.id),
                "theme": interview.theme,
                "user_id": user_id,
                "event": "interview_created",
            },
        )
        return interview
    
    async def get_interview(self, interview_id: UUID, user_id: Optional[str] = None) -> Optional[Interview]:
        """获取访谈详情。如果提供了user_id，则只返回属于该用户的访谈
        
        注意：不缓存 ORM 对象，因为缓存中的 ORM 对象在 session 关闭后会 detached，
        导致后续访问属性时抛出 DetachedInstanceError。
        """
        stmt = select(Interview).where(Interview.id == interview_id)
        if user_id is not None:
            stmt = stmt.where(Interview.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_interview_for_update(self, interview_id: UUID) -> Optional[Interview]:
        """获取 Interview 对象用于更新（绕过缓存，确保绑定到当前 Session）"""
        stmt = select(Interview).where(Interview.id == interview_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_interviews(
        self,
        skip: int = 0,
        limit: int = 20,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple:
        """获取访谈列表。支持用户隔离、状态过滤、主题搜索"""
        from sqlalchemy import or_

        stmt = select(Interview)
        if user_id is not None:
            stmt = stmt.where(Interview.user_id == user_id)
        if status is not None:
            stmt = stmt.where(Interview.status == status)
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Interview.theme.ilike(search_pattern),
                    Interview.background.ilike(search_pattern),
                    Interview.expert_role.ilike(search_pattern),
                )
            )
        stmt = stmt.order_by(desc(Interview.created_at)).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        interviews = result.scalars().all()

        # 获取总数（同样应用过滤）
        count_stmt = select(Interview)
        if user_id is not None:
            count_stmt = count_stmt.where(Interview.user_id == user_id)
        if status is not None:
            count_stmt = count_stmt.where(Interview.status == status)
        if search:
            search_pattern = f"%{search}%"
            count_stmt = count_stmt.where(
                or_(
                    Interview.theme.ilike(search_pattern),
                    Interview.background.ilike(search_pattern),
                    Interview.expert_role.ilike(search_pattern),
                )
            )
        count_result = await self.db.execute(count_stmt)
        total = len(count_result.scalars().all())

        return interviews, total
    
    async def update_interview(self, interview_id: UUID, data: InterviewUpdate) -> Optional[Interview]:
        """更新访谈"""
        interview = await self._get_interview_for_update(interview_id)
        if not interview:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(interview, field, value)

        await self.db.flush()
        await self.db.refresh(interview)
        # 失效访谈缓存
        await interview_cache.invalidate_prefix(f"interview:{interview_id}")
        return interview

    async def delete_interview(self, interview_id: UUID) -> bool:
        """删除访谈（级联删除关联的消息和结构化内容）"""
        interview = await self._get_interview_for_update(interview_id)
        if not interview:
            return False

        await self.db.delete(interview)
        await self.db.flush()
        # 失效缓存
        await interview_cache.invalidate_prefix(f"interview:{interview_id}")
        await structured_content_cache.delete(f"structured:{interview_id}")
        return True
    
    # ==================== Blueprint Generation ====================
    
    async def generate_blueprint(self, interview_id: UUID) -> Dict[str, Any]:
        """生成访谈蓝图"""
        interview = await self.get_interview(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        self.logger.info(
            f"Generating blueprint for interview: {interview_id}",
            extra={"interview_id": str(interview_id), "event": "blueprint_generate_start"},
        )

        # 构建提示词
        formats = interview.target_output_format or [OutputFormat.SCRIPT_CARD.value]
        prompt = prompt_manager.get_blueprint_prompt(
            theme=interview.theme,
            background=interview.background or "",
            expert_role=interview.expert_role or "",
            duration=interview.expected_duration or 30,
            output_format=formats,
        )

        # 调用LLM生成蓝图
        system_prompt = "你是一个专业的经验萃取蓝图设计师。请根据用户输入生成结构化的访谈蓝图。"
        messages = [{"role": "user", "content": prompt}]

        blueprint = await llm_service.generate_json(system_prompt, messages, temperature=0.3)

        # 保存蓝图
        interview.blueprint = blueprint
        await self.db.flush()

        self.logger.info(
            f"Blueprint generated for interview: {interview_id}",
            extra={"interview_id": str(interview_id), "event": "blueprint_generate_complete"},
        )
        return blueprint
    
    # ==================== Message Handling ====================
    
    async def add_message(self, interview_id: UUID, role: str, content: str,
                         message_type: Optional[str] = None,
                         question_type: Optional[str] = None,
                         extracted_data: Optional[Dict] = None,
                         metadata: Optional[Dict] = None) -> Message:
        """添加消息"""
        message = Message(
            interview_id=interview_id,
            role=role,
            content=content,
            message_type=message_type,
            question_type=question_type,
            extracted_data=extracted_data or {},
            extra_metadata=metadata or {},
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message
    
    async def get_messages(self, interview_id: UUID, limit: int = 50) -> List[Message]:
        """获取消息历史"""
        result = await self.db.execute(
            select(Message)
            .where(Message.interview_id == interview_id)
            .order_by(Message.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    # ==================== AI Response Generation ====================
    
    async def generate_opening_question(self, interview_id: UUID) -> Message:
        """生成访谈开场问题（访谈开始时自动调用，无需用户先发送消息）

        采用"四维破冰"开场策略：
        1. 身份共情 —— 精准称呼 + 价值认可
        2. 安全感建立 —— 三不原则（无标准答案、不公开评判、可纠正）
        3. 目标对齐 —— 时长、产出、专家任务
        4. 启动锚定 —— 轻量级、带场景锚点的第一个问题
        """
        interview = await self.get_interview(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        # 构建系统提示词（注入蓝图和专家画像）
        system_prompt = prompt_manager.get_system_prompt({
            "expert_profile": interview.expert_profile or {},
            "blueprint": interview.blueprint,
            "theme": interview.theme,
            "current_step": "event_review",
        })

        # 使用模板化开场提示词（四维破冰）
        opening_prompt = prompt_manager.get_opening_prompt(
            theme=interview.theme,
            background=interview.background or "",
            expert_role=interview.expert_role or "",
            duration=interview.expected_duration or 30,
            output_formats=interview.target_output_format or ["script_card"],
            expert_profile=interview.expert_profile,
            blueprint=interview.blueprint,
        )

        messages = [{"role": "user", "content": opening_prompt}]

        # 生成开场问题
        self.logger.info(
            f"Generating opening question for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "current_state": interview.current_state.value,
                "event": "opening_question_start",
            },
        )
        response = await llm_service.generate_json(system_prompt, messages, temperature=0.7)

        # 保存AI开场消息
        question_data = response.get("question", {})
        ai_content = question_data.get("content")

        # 降级文案：如果LLM返回内容为空或不符合预期，使用结构化回退
        if not ai_content or len(ai_content.strip()) < 50:
            ai_content = self._generate_fallback_opening(
                theme=interview.theme,
                expert_role=interview.expert_role or "",
                duration=interview.expected_duration or 30,
                output_formats=interview.target_output_format or ["script_card"],
            )

        ai_message = await self.add_message(
            interview_id, "assistant", ai_content,
            message_type="question",
            question_type=question_data.get("type", "开场"),
            extracted_data=response.get("structured_update", {}),
            metadata={
                "thinking": response.get("thinking", ""),
                "state_assessment": response.get("state_assessment", {}),
                "is_opening": True,
            }
        )

        # 更新结构化内容
        await self._update_structured_content(interview_id, response.get("structured_update", {}))

        self.logger.info(
            f"Opening question generated for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "question_type": question_data.get("type", "开场"),
                "event": "opening_question_complete",
            },
        )
        return ai_message

    def _generate_fallback_opening(self, theme: str, expert_role: str,
                                   duration: int, output_formats: List[str]) -> str:
        """生成结构化的降级开场白（当LLM输出异常时使用）"""
        format_name_map = {
            "script_card": "话术卡",
            "checklist": "操作检查表",
            "flowchart": "流程图要点",
            "learning_card": "学习卡片",
            "case_study": "案例复盘",
        }
        format_labels = [format_name_map.get(f, f) for f in output_formats]
        output_desc = "、".join(format_labels) if format_labels else "实用工具"

        name = expert_role if expert_role else "老师"

        return (
            f"{name}，您在{theme}方面的实战经验非常宝贵。今天这场访谈的目的，"
            f"是把您脑中的隐性经验转化为一套可以直接给团队新人使用的{output_desc}。\n\n"
            f"整个访谈大约需要 {duration} 分钟。过程中我会不断追问细节，"
            f"可能会有点'打破砂锅问到底'，但这正是为了把您的经验还原到最可操作的粒度。"
            f"您分享的内容没有标准答案，真实发生的就是最好的，"
            f"也仅用于内部经验萃取，不会用作其他用途。\n\n"
            f"咱们直接进入正题。请回忆最近半年内，您在{theme}相关工作中"
            f"印象最深刻的一个真实场景——当时遇到了什么情况，让您觉得这个案例特别值得总结？"
        )

    async def generate_ai_response(self, interview_id: UUID, user_message: str) -> Dict[str, Any]:
        """生成AI回复（非流式，用于蓝图生成等）"""
        interview = await self.get_interview(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        # 保存用户消息
        await self.add_message(interview_id, "user", user_message, message_type="answer")

        # ===== 程序化分析层：专家画像 + 内容分析 =====
        all_messages = await self.get_messages(interview_id, limit=100)
        user_messages = [m.content for m in all_messages if m.role == "user" and m.content]

        # 专家画像分析：第3轮用户回答后首次分析，之后每5轮更新
        if len(user_messages) >= 3:
            should_update_profile = False
            if interview.expert_profile is None or not interview.expert_profile.get("profile_type"):
                should_update_profile = True
            else:
                last_profile_turns = interview.expert_profile.get("analyzed_at_turn", 0)
                if len(user_messages) - last_profile_turns >= 5:
                    should_update_profile = True

            if should_update_profile:
                profile = expert_profiler.analyze(user_messages)
                profile_dict = expert_profiler.to_dict(profile)
                profile_dict["analyzed_at_turn"] = len(user_messages)
                # 关键修复：使用 update() 语句直接更新，避免 detached 对象修改不生效
                from sqlalchemy import update as sa_update
                await self.db.execute(
                    sa_update(Interview)
                    .where(Interview.id == interview_id)
                    .values(expert_profile=profile_dict)
                )
                self.logger.info(
                    f"Expert profile updated for interview: {interview_id}",
                    extra={"interview_id": str(interview_id), "event": "expert_profile_updated"},
                )

        # 内容分析：每轮都进行 - 并行执行独立的预LLM查询
        current_state = interview.current_state.value
        current_state_cn = self.STATE_NAME_MAP.get(current_state, current_state)
        state_goal = self.STATE_GOALS.get(current_state, "深入挖掘专家经验")
        structured, turns, stage_word_count = await asyncio.gather(
            self._get_structured_content(interview_id),
            self._count_turns_in_current_state(interview_id),
            self._get_stage_word_count(interview_id),
        )

        analysis = content_analyzer.full_analysis(
            answer=user_message,
            theme=interview.theme,
            current_step=current_state,
            structured=structured,
            blueprint=interview.blueprint,
            drift_history=interview.drift_history or [],
        )
        analysis_dict = content_analyzer.to_dict(analysis)
        # LLM 灰区仲裁：规则置信度处于 (0.15, 0.35) 时触发语义判定
        # 优化：前1轮不触发灰区仲裁，早期回答天然具有探索性
        if (settings.TOPIC_DRIFT_GRAY_LOWER < analysis.off_topic_confidence < settings.TOPIC_DRIFT_THRESHOLD
                and turns > 1):
            last_question = await self._get_last_ai_question(interview_id)
            llm_drift = await self._detect_topic_drift_llm(
                user_message=user_message,
                theme=interview.theme,
                current_step=current_state,
                state_goal=state_goal,
                last_question=last_question,
            )
            analysis_dict['off_topic'] = llm_drift['is_off_topic']
            analysis_dict['off_topic_confidence'] = llm_drift['confidence']
            analysis_dict['off_topic_reason'] = llm_drift['reason']
            analysis_dict['suggested_correction'] = llm_drift.get('suggested_correction', '')

        # 更新漂移历史
        await self._update_drift_history(interview_id, analysis_dict)

        # 计算时间预算（含阶段差异化字数预算）
        time_budget = self._calculate_time_budget(interview, turns, current_state, stage_word_count)

        # 重新加载 interview 以获取最新的 expert_profile（如果刚更新过）
        interview = await self._get_interview_for_update(interview_id)

        # 构建系统提示词（注入专家画像、蓝图、实时分析结果、时间预算）
        system_prompt = prompt_manager.get_system_prompt({
            "expert_profile": interview.expert_profile or {},
            "blueprint": interview.blueprint,
            "theme": interview.theme,
            "current_step": current_state,
            "content_analysis": analysis_dict,
            "time_budget": time_budget,
        })

        stage_limit = self._calculate_stage_limit(interview)
        system_prompt += f"""\n\n## 当前访谈状态
- 访谈主题：{interview.theme}
- 当前流程阶段：{current_state_cn}（{current_state}）
- 阶段目标：{state_goal}
- 本阶段已进行轮数：{turns}
- 本阶段最大允许轮数：{stage_limit}
- 已萃取结构化内容：{json.dumps(structured, ensure_ascii=False)}
- 目标产出形式：{', '.join(interview.target_output_format or ['script_card'])}

## 时间预算控制（严格执行）
- 访谈总时长：{time_budget['total_duration_min']} 分钟
- 说话速度参考：{time_budget['words_per_minute_range']} 字/分钟
- 当前阶段字数预算：约 {time_budget['stage_word_budget']} 字
- 本阶段已进行：{turns} 轮，剩余可追问：{time_budget['remaining_turns']} 轮
{"【紧急】本阶段时间已用完，请在下一个问题中总结已收集的信息，然后明确告知专家进入下一阶段。" if time_budget['remaining_turns'] <= 0 else "【提醒】本阶段仅剩1轮，请在下一个问题中收集最后的关键信息，然后准备推进到下一阶段。" if time_budget['remaining_turns'] == 1 else ""}
你必须严格控制每个阶段的轮数，不要在一个阶段停留过久。当信息基本收集完毕后，主动推进到下一阶段。

## 重要提醒
你正在进行一场经验萃取访谈，用户（专家）已经回答了上一个问题。请基于用户的回答内容生成下一个深入追问的问题。
- 绝对不要重复之前已经问过的问题（尤其是开场时的自我介绍和"请回忆一个案例"这类问题）。
- 绝对不要再做自我介绍。
- 针对用户回答中的关键信息进行追问，挖掘细节、动作、话术、工具、决策逻辑。
- 如果用户回答跑题或过于空泛，请礼貌地引导其回到具体案例和动作细节。"""

        # 获取历史消息并进行智能截断/摘要（防止长对话导致上下文爆炸和重复提问）
        messages_history = await self.get_messages(interview_id, limit=100)
        messages = []

        # 收集已问问题清单（用于防重复）
        asked_questions = []
        for msg in messages_history:
            if msg.role == "assistant" and msg.content:
                # 只取问题的前80字作为摘要
                q_preview = msg.content[:80].replace("\n", " ")
                asked_questions.append(q_preview)
        asked_questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(asked_questions[-10:])])
        
        # 策略：保留最近6条（约3轮）完整对话，更早的消息压缩为摘要
        recent_count = 6
        recent_messages = messages_history[-recent_count:] if len(messages_history) > recent_count else messages_history
        older_messages = messages_history[:-recent_count] if len(messages_history) > recent_count else []
        
        # 对较早的消息进行压缩摘要
        if older_messages:
            summary_parts = []
            for msg in older_messages:
                preview = msg.content[:120].replace("\n", " ") + "..." if len(msg.content) > 120 else msg.content.replace("\n", " ")
                role_label = "专家" if msg.role == "user" else "访谈者"
                summary_parts.append(f"- [{role_label}] {preview}")
            history_summary = "\n".join(summary_parts)
            messages.append({
                "role": "system",
                "content": f"【历史对话摘要】以下是此前已完成的对话（已压缩，请勿对其中内容重复提问）：\n{history_summary}\n\n【重要】以上历史对话中已涵盖的主题和信息，绝对不要再重复提问。"
            })
        
        # 添加已问问题清单
        if asked_questions_text:
            messages.append({
                "role": "system",
                "content": f"【已提问清单（最近10个）】\n{asked_questions_text}\n\n【硬性规则】你即将生成的问题，绝对不能与上述清单中的任何一个问题在主题或核心问法上重复。如果专家已经详细回答了某类问题，必须换一个新的角度追问，而不是再次询问同样的事情。"
            })
        
        # 最近消息保留完整内容，但过长时截断
        for msg in recent_messages:
            content = msg.content
            if len(content) > 2500:
                content = content[:2500] + "\n...[后续内容较长，核心信息已包含在上述片段中，请基于已有信息继续]"
            messages.append({"role": msg.role, "content": content})
        
        # 添加追问指示
        messages.append({
            "role": "user",
            "content": f"【系统指令】用户已回答上述问题。请基于其回答，针对'{current_state_cn}'阶段的目标，生成下一个深入追问的问题。严禁重复已提问清单中的任何问题。"
        })
        
        # 生成回复
        self.logger.info(
            f"Generating AI response for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "current_state": current_state,
                "turns": turns,
                "event": "ai_response_start",
            },
        )
        response = await llm_service.generate_json(system_prompt, messages, temperature=0.7)

        # 保存AI消息（包含分析元数据）
        ai_content = response.get("question", {}).get("content", "请继续分享您的经验。")
        await self.add_message(
            interview_id, "assistant", ai_content,
            message_type="question",
            question_type=response.get("question", {}).get("type"),
            extracted_data=response.get("structured_update", {}),
            metadata={
                "thinking": response.get("thinking", ""),
                "state_assessment": response.get("state_assessment", {}),
                "content_analysis": analysis_dict,
            }
        )
        
        # 风险标引：规则引擎 + LLM提取双保险
        structured_update = response.get("structured_update", {}) or {}
        rule_risk_result = risk_marker.mark_risks(user_message)
        llm_risks = structured_update.get("risks", []) or []
        merged_risks = risk_marker.merge_with_llm_risks(rule_risk_result.risks_found, llm_risks)
        structured_update["risks"] = merged_risks
        
        # 更新结构化内容
        await self._update_structured_content(interview_id, structured_update)
        
        # 检查状态推进（LLM判断 + 兜底强制推进）
        state_assessment = response.get("state_assessment", {})
        should_advance = state_assessment.get("should_advance", False)
        if await self._should_force_advance(interview_id, state_assessment):
            await self._advance_state(interview_id)

        self.logger.info(
            f"AI response generated for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "current_state": current_state,
                "turns": turns,
                "should_advance": should_advance,
                "event": "ai_response_complete",
            },
        )
        return response

    # ==================== Round Complete (Voice Mode) ====================

    async def complete_round(
        self,
        interview_id: UUID,
        transcription: str,
        notes: List[str],
    ) -> Dict[str, Any]:
        """
        完成当前录音轮次：
        1. LLM 整理转录内容（删除 AI 提问、纠正错别字、去语气词）
        2. 拼接用户备注
        3. 保存为 user message
        4. 生成 AI 下一个问题
        5. 返回整理后的内容 + 两条消息
        """
        interview = await self.get_interview(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        # 获取当前轮次的 AI 提问（最近一条 assistant 消息），用于识别复述内容
        all_messages = await self.get_messages(interview_id, limit=100)
        current_question = ""
        for msg in reversed(all_messages):
            if msg.role == "assistant" and msg.content:
                current_question = msg.content[:500]
                break

        self.logger.info(
            f"Starting round completion for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "transcription_length": len(transcription),
                "notes_count": len(notes),
                "event": "round_complete_start",
            },
        )

        # 1. LLM 整理转录内容
        # 优化：纯文本模式（notes 有意义且 transcription 为空/极短）跳过 LLM 整理
        notes_text = "\n".join(notes) if notes else ""
        has_meaningful_notes = len(notes_text.strip()) >= 20
        if not transcription or not transcription.strip():
            refined = ""
        elif has_meaningful_notes and len(transcription.strip()) < 50:
            # 文本模式为主，转录极短（误触发）：跳过 LLM 整理
            refined = ""
        else:
            refined = await self._refine_transcription(transcription, current_question)

        # 2. 拼接备注
        full_content = refined
        if notes:
            notes_text = "\n".join([f"【备注{i + 1}】{n}" for i, n in enumerate(notes)])
            if refined:
                full_content = f"{refined}\n\n{notes_text}"
            else:
                full_content = notes_text

        # 3. 保存用户消息（手动保存，以便附加 extra_metadata）
        user_msg = await self.add_message(
            interview_id,
            "user",
            full_content,
            message_type="answer",
            metadata={
                "source": "voice_transcription",
                "raw_transcription": transcription,
                "notes": notes,
                "refined_answer": refined,
            },
        )

        # 4. 生成 AI 回复（复用已有逻辑，但不重复保存用户消息）
        ai_response = await self._generate_ai_question_only(interview_id, full_content)

        # 5. 查询最新的 AI 消息
        result = await self.db.execute(
            select(Message)
            .where(Message.interview_id == interview_id)
            .where(Message.role == "assistant")
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        ai_msg = result.scalar_one_or_none()

        self.logger.info(
            f"Round completed for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "refined_length": len(refined),
                "full_length": len(full_content),
                "event": "round_complete",
            },
        )

        return {
            "refined_answer": refined,
            "user_message": user_msg,
            "ai_message": ai_msg,
        }

    def _check_hallucination(self, refined: str, raw: str) -> tuple[bool, str]:
        """
        校验清洗结果是否包含原始转写中没有的实质性新内容（幻觉检测）。
        返回 (是否含幻觉, 问题片段)。
        """
        if not refined:
            return False, ""  # 空字符串是合法的（整段都是复述）

        import re
        # 按句子分割（中/英文标点）
        sentences = [s.strip() for s in re.split(r'[。！？.!?]', refined) if len(s.strip()) >= 5]
        if not sentences:
            return False, ""

        # 原始文本规范化：去除标点、空格
        raw_norm = re.sub(r'[^\w\u4e00-\u9fff]', '', raw)

        for sent in sentences:
            sent_norm = re.sub(r'[^\w\u4e00-\u9fff]', '', sent)
            if len(sent_norm) < 6:
                continue  # 太短的句子不检查

            # 精确子串检查
            if sent_norm in raw_norm:
                continue

            # 模糊匹配：在原始中找最相似的等长片段
            best_ratio = 0.0
            sent_len = len(sent_norm)
            for i in range(max(1, len(raw_norm) - sent_len + 1)):
                chunk = raw_norm[i:i + sent_len]
                if len(chunk) < sent_len:
                    continue
                matches = sum(1 for a, b in zip(sent_norm, chunk) if a == b)
                ratio = matches / sent_len
                if ratio > best_ratio:
                    best_ratio = ratio

            # 如果最佳匹配率 < 60%，认为这个句子是编造的
            if best_ratio < 0.6:
                return True, sent[:40]

        return False, ""

    async def _refine_transcription(self, transcription: str, current_question: str) -> str:
        """使用 LLM 整理转录内容：删除访谈人复述提问、仅保留被访谈人回答、纠正错别字、去语气词"""
        if not transcription.strip():
            return ""

        system_prompt = (
            "你是一个语音转录文本清洗专家。下面提供的是一段访谈录音的语音识别结果。\n\n"
            "【最高优先级规则——严禁编造】\n"
            "你绝对不允许增加、补充、推测或编造任何专家没有说过的内容。"
            "你的输出必须是原始转写内容的严格子集（仅做删除和极少量错别字纠正）。\n"
            "如果转写中只有复述提问、没有任何回答，answer_only 必须是空字符串，"
            "不要试图补全、推测或生成回答。\n\n"
            "【录音场景说明】\n"
            "这是一个AI辅助的经验萃取访谈。录音中会出现两个角色：\n"
            "1. 访谈人（主持人）：负责将AI系统给出的问题念给被访谈人听\n"
            "2. 被访谈人（专家）：听到问题后，分享自己的经验、案例和方法\n"
            "由于录音全程开启，转写内容中同时包含了访谈人复述提问和被访谈人回答两部分。\n\n"
            "【你的任务】\n"
            "删除访谈人复述AI提问的内容，仅保留被访谈人的回答内容。\n\n"
            "【判断标准——如何区分\"复述提问\"和\"回答\"】\n"
            "复述提问的特征：\n"
            "- 内容较短，与\"当前AI问题\"高度相似甚至逐字重复\n"
            "- 通常出现在转写内容的开头部分\n"
            "- 语气是提问式（以问号结尾，或使用\"能不能\"\"请谈谈\"等措辞）\n"
            "- 不包含具体案例、数据、经验细节\n\n"
            "回答的特征：\n"
            "- 内容较长，包含具体的经验描述、案例细节、数据、方法论\n"
            "- 是对问题的实质性回应，而非重复问题本身\n"
            "- 被访谈人可能在回答开头提及问题中的关键词（如\"关于客户开发，我的做法是...\"），"
            "这是正常的回答引入，必须保留\n"
            "- 包含时间、地点、人物、动作、结果等叙事要素\n\n"
            "【处理规则】\n"
            "1. 只删除明显是逐字复述提问的内容，不要删减被访谈人的回答\n"
            "2. 被访谈人在回答中引用问题关键词是正常行为，保留\n"
            "3. 纠正语音识别产生的明显错别字（如\"的/地/得\"、同音字）\n"
            "4. 删除无意义的语气词和口头禅（如'嗯''啊''那个''就是''然后然后'等），"
            "但保留有表达功能的语气词（如'确实''其实''当然'）\n"
            "5. 删除明显重复、卡顿造成的冗余片段\n"
            "6. 保持被访谈人回答的完整性，不调整语序，不增加内容\n"
            "7. 如果整段都是复述提问（专家还没开始回答），answer_only 必须是空字符串\n\n"
            "【输出格式】\n"
            "必须返回JSON，包含以下字段：\n"
            "- analysis: 简要分析，指出哪些部分是复述提问、哪些部分是回答（50字以内）\n"
            "- answer_only: 仅保留被访谈人回答的清洗后文本。"
            "如果只有复述没有回答，该字段必须是空字符串\"\"\n"
            "- confidence: 你对区分结果的确信程度，0.0-1.0\n"
            "\n示例1（有回答）：\n"
            '{"analysis": "开头\"请谈谈你的销售经验\"是复述提问，其余为回答", '
            '"answer_only": "我做销售大概十年了，印象最深的一次是...", "confidence": 0.95}\n'
            "\n示例2（只有复述，没有回答）：\n"
            '{"analysis": "整段都是复述AI提问，无回答内容", '
            '"answer_only": "", "confidence": 0.98}'
        )

        content = f"【当前轮次的AI问题】\n{current_question or '（无）'}\n\n"
        content += f"【语音识别原始文字】\n{transcription}\n\n"
        content += "请按照上述规则和格式，返回JSON。"

        messages = [{"role": "user", "content": content}]

        try:
            result = await llm_service.generate_json(
                system_prompt, messages, temperature=0.0, max_tokens=3000
            )
            refined = result.get("answer_only", "")
            if not refined:
                # 兼容旧字段名
                refined = (
                    result.get("refined_text")
                    or result.get("content")
                    or result.get("result")
                    or ""
                )

            refined = refined.strip()
            raw_len = len(transcription.strip())
            refined_len = len(refined)

            # 防御性检查1：过度清洗（长度异常短）
            if raw_len > 50 and refined_len < raw_len * 0.3:
                self.logger.warning(
                    f"Refined text suspiciously short ({refined_len}/{raw_len}), using raw",
                    extra={
                        "raw_length": raw_len,
                        "refined_length": refined_len,
                        "confidence": result.get("confidence"),
                        "analysis": result.get("analysis"),
                        "event": "refine_over_cleaning_fallback",
                    },
                )
                return transcription.strip()

            # 防御性检查2：幻觉检测（清洗结果包含原始中没有的内容）
            has_hallucination, bad_fragment = self._check_hallucination(refined, transcription)
            if has_hallucination:
                self.logger.warning(
                    f"Hallucination detected in refined text, using raw. Bad fragment: {bad_fragment}",
                    extra={
                        "raw_length": raw_len,
                        "refined_length": refined_len,
                        "bad_fragment": bad_fragment,
                        "confidence": result.get("confidence"),
                        "analysis": result.get("analysis"),
                        "event": "refine_hallucination_fallback",
                    },
                )
                return transcription.strip()

            self.logger.info(
                f"Transcription refined: {raw_len} -> {refined_len} chars",
                extra={
                    "raw_length": raw_len,
                    "refined_length": refined_len,
                    "confidence": result.get("confidence"),
                    "analysis": result.get("analysis"),
                    "event": "refine_transcription_success",
                },
            )
            return refined
        except Exception as e:
            self.logger.warning(
                f"Transcription refinement failed, returning raw: {e}",
                extra={"event": "refine_transcription_fallback"},
            )
            return transcription.strip()

    async def _generate_ai_question_only(self, interview_id: UUID, user_message: str) -> Dict[str, Any]:
        """
        仅生成 AI 问题（不保存用户消息，假设用户消息已由调用方保存）
        逻辑与 generate_ai_response 基本一致，但跳过 user message 保存
        """
        interview = await self.get_interview(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        # ===== 程序化分析层：专家画像 + 内容分析 =====
        all_messages = await self.get_messages(interview_id, limit=100)
        user_messages = [m.content for m in all_messages if m.role == "user" and m.content]

        # 专家画像分析
        if len(user_messages) >= 3:
            should_update_profile = False
            if interview.expert_profile is None or not interview.expert_profile.get("profile_type"):
                should_update_profile = True
            else:
                last_profile_turns = interview.expert_profile.get("analyzed_at_turn", 0)
                if len(user_messages) - last_profile_turns >= 5:
                    should_update_profile = True

            if should_update_profile:
                profile = expert_profiler.analyze(user_messages)
                profile_dict = expert_profiler.to_dict(profile)
                profile_dict["analyzed_at_turn"] = len(user_messages)
                from sqlalchemy import update as sa_update
                await self.db.execute(
                    sa_update(Interview)
                    .where(Interview.id == interview_id)
                    .values(expert_profile=profile_dict)
                )
                self.logger.info(
                    f"Expert profile updated for interview: {interview_id}",
                    extra={"interview_id": str(interview_id), "event": "expert_profile_updated"},
                )

        # 内容分析 - 并行执行独立的预LLM查询
        current_state = interview.current_state.value
        current_state_cn = self.STATE_NAME_MAP.get(current_state, current_state)
        state_goal = self.STATE_GOALS.get(current_state, "深入挖掘专家经验")
        structured, turns, stage_word_count = await asyncio.gather(
            self._get_structured_content(interview_id),
            self._count_turns_in_current_state(interview_id),
            self._get_stage_word_count(interview_id),
        )

        analysis = content_analyzer.full_analysis(
            answer=user_message,
            theme=interview.theme,
            current_step=current_state,
            structured=structured,
            blueprint=interview.blueprint,
            drift_history=interview.drift_history or [],
        )
        analysis_dict = content_analyzer.to_dict(analysis)
        # LLM 灰区仲裁：规则置信度处于 (0.15, 0.35) 时触发语义判定
        # 优化：前1轮不触发灰区仲裁，早期回答天然具有探索性
        if (settings.TOPIC_DRIFT_GRAY_LOWER < analysis.off_topic_confidence < settings.TOPIC_DRIFT_THRESHOLD
                and turns > 1):
            last_question = await self._get_last_ai_question(interview_id)
            llm_drift = await self._detect_topic_drift_llm(
                user_message=user_message,
                theme=interview.theme,
                current_step=current_state,
                state_goal=state_goal,
                last_question=last_question,
            )
            analysis_dict['off_topic'] = llm_drift['is_off_topic']
            analysis_dict['off_topic_confidence'] = llm_drift['confidence']
            analysis_dict['off_topic_reason'] = llm_drift['reason']
            analysis_dict['suggested_correction'] = llm_drift.get('suggested_correction', '')

        # 更新漂移历史
        await self._update_drift_history(interview_id, analysis_dict)

        time_budget = self._calculate_time_budget(interview, turns, current_state, stage_word_count)
        interview = await self._get_interview_for_update(interview_id)

        # 构建系统提示词
        system_prompt = prompt_manager.get_system_prompt({
            "expert_profile": interview.expert_profile or {},
            "blueprint": interview.blueprint,
            "theme": interview.theme,
            "current_step": current_state,
            "content_analysis": analysis_dict,
            "time_budget": time_budget,
        })

        stage_limit = self._calculate_stage_limit(interview)
        system_prompt += f"""\n\n## 当前访谈状态
- 访谈主题：{interview.theme}
- 当前流程阶段：{current_state_cn}（{current_state}）
- 阶段目标：{state_goal}
- 本阶段已进行轮数：{turns}
- 本阶段最大允许轮数：{stage_limit}
- 已萃取结构化内容：{json.dumps(structured, ensure_ascii=False)}
- 目标产出形式：{', '.join(interview.target_output_format or ['script_card'])}

## 时间预算控制（严格执行）
- 访谈总时长：{time_budget['total_duration_min']} 分钟
- 说话速度参考：{time_budget['words_per_minute_range']} 字/分钟
- 当前阶段字数预算：约 {time_budget['stage_word_budget']} 字
- 本阶段已进行：{turns} 轮，剩余可追问：{time_budget['remaining_turns']} 轮
{"【紧急】本阶段时间已用完，请在下一个问题中总结已收集的信息，然后明确告知专家进入下一阶段。" if time_budget['remaining_turns'] <= 0 else "【提醒】本阶段仅剩1轮，请在下一个问题中收集最后的关键信息，然后准备推进到下一阶段。" if time_budget['remaining_turns'] == 1 else ""}
你必须严格控制每个阶段的轮数，不要在一个阶段停留过久。当信息基本收集完毕后，主动推进到下一阶段。

## 重要提醒
你正在进行一场经验萃取访谈，用户（专家）已经回答了上一个问题。请基于用户的回答内容生成下一个深入追问的问题。
- 绝对不要重复之前已经问过的问题（尤其是开场时的自我介绍和"请回忆一个案例"这类问题）。
- 绝对不要再做自我介绍。
- 针对用户回答中的关键信息进行追问，挖掘细节、动作、话术、工具、决策逻辑。
- 如果用户回答跑题或过于空泛，请礼貌地引导其回到具体案例和动作细节。"""

        # 获取历史消息并进行智能截断/摘要
        messages_history = await self.get_messages(interview_id, limit=100)
        messages = []

        asked_questions = []
        for msg in messages_history:
            if msg.role == "assistant" and msg.content:
                q_preview = msg.content[:80].replace("\n", " ")
                asked_questions.append(q_preview)
        asked_questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(asked_questions[-10:])])

        recent_count = 6
        recent_messages = messages_history[-recent_count:] if len(messages_history) > recent_count else messages_history
        older_messages = messages_history[:-recent_count] if len(messages_history) > recent_count else []

        if older_messages:
            summary_parts = []
            for msg in older_messages:
                preview = msg.content[:120].replace("\n", " ") + "..." if len(msg.content) > 120 else msg.content.replace("\n", " ")
                role_label = "专家" if msg.role == "user" else "访谈者"
                summary_parts.append(f"- [{role_label}] {preview}")
            history_summary = "\n".join(summary_parts)
            messages.append({
                "role": "system",
                "content": f"【历史对话摘要】以下是此前已完成的对话（已压缩，请勿对其中内容重复提问）：\n{history_summary}\n\n【重要】以上历史对话中已涵盖的主题和信息，绝对不要再重复提问。"
            })

        if asked_questions_text:
            messages.append({
                "role": "system",
                "content": f"【已提问清单（最近10个）】\n{asked_questions_text}\n\n【硬性规则】你即将生成的问题，绝对不能与上述清单中的任何一个问题在主题或核心问法上重复。如果专家已经详细回答了某类问题，必须换一个新的角度追问，而不是再次询问同样的事情。"
            })

        for msg in recent_messages:
            content = msg.content
            if len(content) > 2500:
                content = content[:2500] + "\n...[后续内容较长，核心信息已包含在上述片段中，请基于已有信息继续]"
            messages.append({"role": msg.role, "content": content})

        messages.append({
            "role": "user",
            "content": f"【系统指令】用户已回答上述问题。请基于其回答，针对'{current_state_cn}'阶段的目标，生成下一个深入追问的问题。严禁重复已提问清单中的任何问题。"
        })

        self.logger.info(
            f"Generating AI question for round complete: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "current_state": current_state,
                "turns": turns,
                "event": "ai_question_start",
            },
        )
        response = await llm_service.generate_json(system_prompt, messages, temperature=0.7)

        # 保存 AI 消息
        ai_content = response.get("question", {}).get("content", "请继续分享您的经验。")
        await self.add_message(
            interview_id, "assistant", ai_content,
            message_type="question",
            question_type=response.get("question", {}).get("type"),
            extracted_data=response.get("structured_update", {}),
            metadata={
                "thinking": response.get("thinking", ""),
                "state_assessment": response.get("state_assessment", {}),
                "content_analysis": analysis_dict,
            }
        )

        # 风险标引
        structured_update = response.get("structured_update", {}) or {}
        rule_risk_result = risk_marker.mark_risks(user_message)
        llm_risks = structured_update.get("risks", []) or []
        merged_risks = risk_marker.merge_with_llm_risks(rule_risk_result.risks_found, llm_risks)
        structured_update["risks"] = merged_risks

        await self._update_structured_content(interview_id, structured_update)

        # 检查状态推进
        state_assessment = response.get("state_assessment", {})
        should_advance = state_assessment.get("should_advance", False)
        if await self._should_force_advance(interview_id, state_assessment):
            await self._advance_state(interview_id)

        self.logger.info(
            f"AI question generated for round complete: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "current_state": current_state,
                "turns": turns,
                "should_advance": should_advance,
                "event": "ai_question_complete",
            },
        )
        return response

    async def generate_ai_response_stream(self, interview_id: UUID, user_message: str):
        """生成AI回复（流式，用于实时对话）"""
        interview = await self.get_interview(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        # 保存用户消息
        await self.add_message(interview_id, "user", user_message, message_type="answer")

        # ===== 程序化分析层：专家画像 + 内容分析 =====
        all_messages = await self.get_messages(interview_id, limit=100)
        user_messages = [m.content for m in all_messages if m.role == "user" and m.content]

        # 专家画像分析：第3轮用户回答后首次分析，之后每5轮更新
        if len(user_messages) >= 3:
            should_update_profile = False
            if interview.expert_profile is None or not interview.expert_profile.get("profile_type"):
                should_update_profile = True
            else:
                last_profile_turns = interview.expert_profile.get("analyzed_at_turn", 0)
                if len(user_messages) - last_profile_turns >= 5:
                    should_update_profile = True

            if should_update_profile:
                profile = expert_profiler.analyze(user_messages)
                profile_dict = expert_profiler.to_dict(profile)
                profile_dict["analyzed_at_turn"] = len(user_messages)
                # 关键修复：使用 update() 语句直接更新，避免 detached 对象修改不生效
                from sqlalchemy import update as sa_update
                await self.db.execute(
                    sa_update(Interview)
                    .where(Interview.id == interview_id)
                    .values(expert_profile=profile_dict)
                )
                self.logger.info(
                    f"Expert profile updated for interview: {interview_id}",
                    extra={"interview_id": str(interview_id), "event": "expert_profile_updated"},
                )

        # 内容分析：每轮都进行
        structured = await self._get_structured_content(interview_id)
        current_state = interview.current_state.value
        current_state_cn = self.STATE_NAME_MAP.get(current_state, current_state)
        state_goal = self.STATE_GOALS.get(current_state, "深入挖掘专家经验")
        turns = await self._count_turns_in_current_state(interview_id)
        stage_word_count = await self._get_stage_word_count(interview_id)

        analysis = content_analyzer.full_analysis(
            answer=user_message,
            theme=interview.theme,
            current_step=current_state,
            structured=structured,
            blueprint=interview.blueprint,
            drift_history=interview.drift_history or [],
        )
        analysis_dict = content_analyzer.to_dict(analysis)
        # LLM 灰区仲裁：规则置信度处于 (0.15, 0.35) 时触发语义判定
        # 优化：前1轮不触发灰区仲裁，早期回答天然具有探索性
        if (settings.TOPIC_DRIFT_GRAY_LOWER < analysis.off_topic_confidence < settings.TOPIC_DRIFT_THRESHOLD
                and turns > 1):
            last_question = await self._get_last_ai_question(interview_id)
            llm_drift = await self._detect_topic_drift_llm(
                user_message=user_message,
                theme=interview.theme,
                current_step=current_state,
                state_goal=state_goal,
                last_question=last_question,
            )
            analysis_dict['off_topic'] = llm_drift['is_off_topic']
            analysis_dict['off_topic_confidence'] = llm_drift['confidence']
            analysis_dict['off_topic_reason'] = llm_drift['reason']
            analysis_dict['suggested_correction'] = llm_drift.get('suggested_correction', '')

        # 更新漂移历史
        await self._update_drift_history(interview_id, analysis_dict)

        # 计算时间预算（含阶段差异化字数预算）
        time_budget = self._calculate_time_budget(interview, turns, current_state, stage_word_count)

        # 重新加载 interview 以获取最新的 expert_profile（如果刚更新过）
        interview = await self._get_interview_for_update(interview_id)

        # 构建系统提示词（注入专家画像、蓝图、实时分析结果、时间预算）
        system_prompt = prompt_manager.get_system_prompt({
            "expert_profile": interview.expert_profile or {},
            "blueprint": interview.blueprint,
            "theme": interview.theme,
            "current_step": current_state,
            "content_analysis": analysis_dict,
            "time_budget": time_budget,
        })

        stage_limit = self._calculate_stage_limit(interview)
        system_prompt += f"""\n\n## 当前访谈状态
- 访谈主题：{interview.theme}
- 当前流程阶段：{current_state_cn}（{current_state}）
- 阶段目标：{state_goal}
- 本阶段已进行轮数：{turns}
- 本阶段最大允许轮数：{stage_limit}
- 已萃取结构化内容：{json.dumps(structured, ensure_ascii=False)}
- 目标产出形式：{', '.join(interview.target_output_format or ['script_card'])}

## 时间预算控制（严格执行）
- 访谈总时长：{time_budget['total_duration_min']} 分钟
- 说话速度参考：{time_budget['words_per_minute_range']} 字/分钟
- 当前阶段字数预算：约 {time_budget['stage_word_budget']} 字
- 本阶段已进行：{turns} 轮，剩余可追问：{time_budget['remaining_turns']} 轮
{"【紧急】本阶段时间已用完，请在下一个问题中总结已收集的信息，然后明确告知专家进入下一阶段。" if time_budget['remaining_turns'] <= 0 else "【提醒】本阶段仅剩1轮，请在下一个问题中收集最后的关键信息，然后准备推进到下一阶段。" if time_budget['remaining_turns'] == 1 else ""}
你必须严格控制每个阶段的轮数，不要在一个阶段停留过久。当信息基本收集完毕后，主动推进到下一阶段。

## 重要提醒
你正在进行一场经验萃取访谈，用户（专家）已经回答了上一个问题。请基于用户的回答内容生成下一个深入追问的问题。
- 绝对不要重复之前已经问过的问题（尤其是开场时的自我介绍和"请回忆一个案例"这类问题）。
- 绝对不要再做自我介绍。
- 针对用户回答中的关键信息进行追问，挖掘细节、动作、话术、工具、决策逻辑。
- 如果用户回答跑题或过于空泛，请礼貌地引导其回到具体案例和动作细节。"""

        # 获取历史消息并进行智能截断/摘要（防止长对话导致上下文爆炸和重复提问）
        messages_history = await self.get_messages(interview_id, limit=100)
        messages = []

        # 收集已问问题清单（用于防重复）
        asked_questions = []
        for msg in messages_history:
            if msg.role == "assistant" and msg.content:
                q_preview = msg.content[:80].replace("\n", " ")
                asked_questions.append(q_preview)
        asked_questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(asked_questions[-10:])])
        
        # 策略：保留最近6条（约3轮）完整对话，更早的消息压缩为摘要
        recent_count = 6
        recent_messages = messages_history[-recent_count:] if len(messages_history) > recent_count else messages_history
        older_messages = messages_history[:-recent_count] if len(messages_history) > recent_count else []
        
        # 对较早的消息进行压缩摘要
        if older_messages:
            summary_parts = []
            for msg in older_messages:
                preview = msg.content[:120].replace("\n", " ") + "..." if len(msg.content) > 120 else msg.content.replace("\n", " ")
                role_label = "专家" if msg.role == "user" else "访谈者"
                summary_parts.append(f"- [{role_label}] {preview}")
            history_summary = "\n".join(summary_parts)
            messages.append({
                "role": "system",
                "content": f"【历史对话摘要】以下是此前已完成的对话（已压缩，请勿对其中内容重复提问）：\n{history_summary}\n\n【重要】以上历史对话中已涵盖的主题和信息，绝对不要再重复提问。"
            })
        
        # 添加已问问题清单
        if asked_questions_text:
            messages.append({
                "role": "system",
                "content": f"【已提问清单（最近10个）】\n{asked_questions_text}\n\n【硬性规则】你即将生成的问题，绝对不能与上述清单中的任何一个问题在主题或核心问法上重复。如果专家已经详细回答了某类问题，必须换一个新的角度追问，而不是再次询问同样的事情。"
            })
        
        # 最近消息保留完整内容，但过长时截断
        for msg in recent_messages:
            content = msg.content
            if len(content) > 2500:
                content = content[:2500] + "\n...[后续内容较长，核心信息已包含在上述片段中，请基于已有信息继续]"
            messages.append({"role": msg.role, "content": content})
        
        # 添加追问指示
        messages.append({
            "role": "user",
            "content": f"【系统指令】用户已回答上述问题。请基于其回答，针对'{current_state_cn}'阶段的目标，生成下一个深入追问的问题。严禁重复已提问清单中的任何问题。"
        })
        
        # 流式生成
        self.logger.info(
            f"Generating AI stream response for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "current_state": current_state,
                "turns": turns,
                "event": "ai_stream_response_start",
            },
        )
        full_response = ""
        async for chunk in llm_service.generate_stream(system_prompt, messages, temperature=0.7):
            full_response += chunk
            yield chunk

        # 解析完整响应
        try:
            response_data = json.loads(full_response)
            ai_content = response_data.get("question", {}).get("content", full_response)

            # 保存AI消息（包含分析元数据）
            await self.add_message(
                interview_id, "assistant", ai_content,
                message_type="question",
                question_type=response_data.get("question", {}).get("type"),
                extracted_data=response_data.get("structured_update", {}),
                metadata={
                    "thinking": response_data.get("thinking", ""),
                    "state_assessment": response_data.get("state_assessment", {}),
                    "content_analysis": analysis_dict,
                }
            )

            # 风险标引：规则引擎 + LLM提取双保险
            structured_update = response_data.get("structured_update", {}) or {}
            rule_risk_result = risk_marker.mark_risks(user_message)
            llm_risks = structured_update.get("risks", []) or []
            merged_risks = risk_marker.merge_with_llm_risks(rule_risk_result.risks_found, llm_risks)
            structured_update["risks"] = merged_risks

            # 更新结构化内容
            await self._update_structured_content(interview_id, structured_update)

            # 检查状态推进（LLM判断 + 兜底强制推进）
            state_assessment = response_data.get("state_assessment", {})
            should_advance = state_assessment.get("should_advance", False)
            if await self._should_force_advance(interview_id, state_assessment):
                await self._advance_state(interview_id)

            self.logger.info(
                f"AI stream response completed for interview: {interview_id}",
                extra={
                    "interview_id": str(interview_id),
                    "current_state": current_state,
                    "should_advance": should_advance,
                    "event": "ai_stream_response_complete",
                },
            )
        except json.JSONDecodeError:
            # 如果不是JSON格式，直接保存文本
            await self.add_message(
                interview_id, "assistant", full_response,
                message_type="question",
            )
            self.logger.warning(
                f"AI stream response JSON decode failed for interview: {interview_id}",
                extra={
                    "interview_id": str(interview_id),
                    "response_length": len(full_response),
                    "event": "ai_stream_response_json_decode_error",
                },
            )
    
    # ==================== State Management ====================
    
    # 状态名称中英文映射（用于匹配LLM返回的中文状态名）
    STATE_NAME_MAP = {
        "event_review": "复盘事件",
        "framework_build": "建构框架",
        "detail_mining": "挖掘细节",
        "obstacle_identify": "识别障碍",
        "tool_extract": "提炼工具",
        "confirmation": "复述确认",
        "completed": "已完成",
    }
    
    # 各阶段目标描述
    STATE_GOALS = {
        "event_review": "引导专家完整描述一个典型案例的背景、冲突、行动和结果。已获取案例后，应深入追问关键动作细节，不要停留在表面描述。",
        "framework_build": "基于已描述的案例，提炼核心方法论框架（如步骤、原则、关键决策点）。追问专家归纳总结其隐性经验结构。",
        "detail_mining": "针对每个关键步骤，深挖具体操作细节：用了什么话术？做了什么动作？用了什么工具？当时是怎么想的？",
        "obstacle_identify": "识别该场景下的常见误区、困难点和失败案例。追问专家'新手最容易犯什么错'、'如果重来会避开什么'。",
        "tool_extract": "将经验转化为可直接使用的工具：话术模板、检查表、流程图要点、口诀等。追问专家是否有现成的文档或模板。",
        "confirmation": "复述已萃取的核心内容，请专家确认准确性。如有偏差，请专家纠正并补充。",
    }

    # ========== LLM 语义主题偏离检测（灰区仲裁）==========

    async def _get_last_ai_question(self, interview_id: UUID) -> str:
        """获取最近一条 AI 提问的内容"""
        messages = await self.get_messages(interview_id, limit=20)
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.content:
                return msg.content
        return ""

    async def _detect_topic_drift_llm(
        self,
        user_message: str,
        theme: str,
        current_step: str,
        state_goal: str,
        last_question: str,
    ) -> Dict[str, Any]:
        """LLM 语义主题偏离检测（灰区仲裁）

        当规则引擎置信度处于灰区 (0.15, 0.35) 时，调用 LLM 进行语义判定。
        返回结果与 detect_off_topic 格式兼容。
        """
        system_prompt = prompt_manager.render("tasks/topic_drift_arbitration_system.md", {})
        user_prompt = prompt_manager.render("tasks/topic_drift_arbitration_user.md", {
            "theme": theme,
            "current_step": current_step,
            "state_goal": state_goal,
            "last_question": last_question,
            "user_message": user_message,
        })

        try:
            result = await llm_service.generate_json(
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.0,
                max_tokens=500,
            )
            is_off_topic = bool(result.get("is_off_topic", False))
            confidence = float(result.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            reason = str(result.get("reason", "LLM语义判定完成"))
            suggested_correction = str(result.get("suggested_correction", ""))

            self.logger.info(
                "LLM topic drift arbitration completed",
                extra={
                    "event": "topic_drift_llm_arbitration",
                    "is_off_topic": is_off_topic,
                    "confidence": confidence,
                    "current_step": current_step,
                },
            )
            return {
                "is_off_topic": is_off_topic,
                "confidence": confidence,
                "reason": f"【LLM语义判定】{reason}",
                "suggested_correction": suggested_correction,
            }
        except Exception as e:
            self.logger.error(
                f"LLM topic drift detection failed: {e}",
                extra={"event": "topic_drift_llm_error", "current_step": current_step},
                exc_info=True,
            )
            # 出错时保守处理：不判定为偏离
            return {
                "is_off_topic": False,
                "confidence": 0.1,
                "reason": "LLM语义判定出错，采用保守策略（不偏离）",
                "suggested_correction": "",
            }

    async def _update_drift_history(self, interview_id: UUID, analysis_dict: Dict[str, Any]) -> None:
        """更新访谈的漂移历史记录（保留最近 max_history 条）"""
        interview = await self.get_interview(interview_id)
        if not interview:
            return

        history = list(interview.drift_history or [])
        history.append({
            "confidence": analysis_dict.get("off_topic_confidence", 0),
            "is_off_topic": analysis_dict.get("off_topic", False),
            "reason": analysis_dict.get("off_topic_reason", ""),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # 保留最近 max_history 条
        max_history = content_analyzer.max_history
        if len(history) > max_history:
            history = history[-max_history:]

        from sqlalchemy import update as sa_update
        await self.db.execute(
            sa_update(Interview)
            .where(Interview.id == interview_id)
            .values(drift_history=history)
        )

    async def _count_turns_in_current_state(self, interview_id: UUID) -> int:
        """统计当前状态下已进行的AI提问轮数（含开场问题）"""
        cache_key = f"turns_count:{interview_id}"
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        interview = await self.get_interview(interview_id)
        if not interview:
            return 0

        messages = await self.get_messages(interview_id, limit=100)
        current_state = interview.current_state.value

        # 优先方法：使用 state_history 中的转换时间作为分界
        history = interview.state_history or []
        last_transition_time = None
        if history:
            # 新格式使用 transitioned_at，旧格式使用 timestamp
            last_transition_time = history[-1].get("transitioned_at") or history[-1].get("timestamp")

        count = 0
        checked = 0
        for msg in reversed(messages):
            if msg.role != "assistant":
                continue
            checked += 1

            # 方法1：如果有状态转换时间，用时间分界（最可靠）
            if last_transition_time and msg.created_at:
                try:
                    from datetime import datetime
                    # 兼容两种ISO格式：带T的和不带T的
                    ts = last_transition_time
                    if "T" not in ts and " " in ts:
                        ts = ts.replace(" ", "T", 1)
                    transition_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    # 消息时间在转换时间之前 → 属于旧状态
                    if msg.created_at.replace(tzinfo=None) <= transition_dt.replace(tzinfo=None):
                        break
                except (ValueError, TypeError, AttributeError):
                    pass  # 解析失败，回退到方法2

            # 方法2：使用 metadata 中的 current_step 匹配（鲁棒版本）
            state_meta = msg.extra_metadata.get("state_assessment", {}) if msg.extra_metadata else {}
            # 关键修复：处理 current_step 为 None 或空字符串的情况
            msg_state = state_meta.get("current_step") or current_state
            normalized_msg_state = self._normalize_state_name(msg_state)
            normalized_current_state = self._normalize_state_name(current_state)

            if normalized_msg_state == normalized_current_state:
                count += 1
            else:
                self.logger.info(
                    f"Turn counting break at msg {msg.id}: state mismatch",
                    extra={
                        "interview_id": str(interview_id),
                        "msg_id": str(msg.id),
                        "msg_state": msg_state,
                        "current_state": current_state,
                        "event": "turn_count_break",
                    },
                )
                break

        self.logger.info(
            f"Counted {count} turns in current state for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "current_state": current_state,
                "assistant_messages_checked": checked,
                "turns_counted": count,
                "event": "turn_count_complete",
            },
        )
        self._query_cache[cache_key] = count
        return count

    # 第四层兜底：AI回复内容饱和度检测触发词
    # 当AI回复中出现这些措辞时，说明AI已经在尝试推进，但should_advance可能为false
    _ADVANCE_TRIGGER_PHRASES = [
        "接下来进入下一阶段",
        "进入下一阶段",
        "进入下一环节",
        "进入下一个阶段",
        "我们进入",
        "接下来我们",
        "进入框架",
        "进入细节",
        "进入障碍",
        "进入工具",
        "进入确认",
        "阶段结束",
        "本阶段结束",
        "阶段完成",
        "本阶段完成",
    ]

    async def _should_force_advance(self, interview_id: UUID, state_assessment: Dict[str, Any]) -> bool:
        """判断是否应强制推进状态（五层兜底机制）"""
        interview = await self.get_interview(interview_id)
        if not interview:
            return False
        current_state = interview.current_state.value

        # ===== 第1层：LLM主动建议 =====
        should_advance = state_assessment.get("should_advance", False)
        if isinstance(should_advance, str):
            should_advance = should_advance.lower() == "true"

        if should_advance:
            self.logger.info(
                f"LLM recommends advance for interview: {interview_id}",
                extra={
                    "interview_id": str(interview_id),
                    "should_advance": should_advance,
                    "event": "llm_recommend_advance",
                },
            )
            return True

        # ===== 第2层：字数上限兜底 =====
        stage_word_count = await self._get_stage_word_count(interview_id)
        total_word_budget = (interview.expected_duration or 30) * self.WORDS_PER_MINUTE
        ratio = self.STATE_WORD_DURATION_RATIOS.get(current_state, 1 / 6)
        stage_word_limit = int(total_word_budget * ratio)

        if stage_word_count >= stage_word_limit:
            self.logger.info(
                f"Force advance by word limit for interview: {interview_id}",
                extra={
                    "interview_id": str(interview_id),
                    "current_state": current_state,
                    "stage_word_count": stage_word_count,
                    "stage_word_limit": stage_word_limit,
                    "event": "force_advance_word_limit",
                },
            )
            return True

        # ===== 第3层：轮数上限兜底 =====
        turns = await self._count_turns_in_current_state(interview_id)
        stage_limit = self._calculate_stage_limit(interview)
        if turns >= stage_limit:
            self.logger.info(
                f"Force advance by turn limit for interview: {interview_id}",
                extra={
                    "interview_id": str(interview_id),
                    "current_state": current_state,
                    "turns": turns,
                    "stage_limit": stage_limit,
                    "event": "force_advance_turn_limit",
                },
            )
            return True

        # ===== 第4层：内容饱和度检测（AI措辞兜底） =====
        # 如果AI回复中已出现"进入下一阶段"等措辞，但should_advance为false，说明LLM行为不一致
        messages = await self.get_messages(interview_id, limit=20)
        if messages:
            last_ai_msg = None
            for msg in reversed(messages):
                if msg.role == "assistant" and msg.content:
                    last_ai_msg = msg
                    break
            if last_ai_msg and last_ai_msg.content:
                content_lower = last_ai_msg.content.lower()
                for phrase in self._ADVANCE_TRIGGER_PHRASES:
                    if phrase.lower() in content_lower:
                        self.logger.info(
                            f"Force advance by content saturation trigger for interview: {interview_id}",
                            extra={
                                "interview_id": str(interview_id),
                                "current_state": current_state,
                                "trigger_phrase": phrase,
                                "event": "force_advance_content_saturation",
                            },
                        )
                        return True

        # ===== 第5层：绝对时间上限兜底 =====
        # 计算当前阶段已消耗的"等效时间"（基于字数/语速），若超过阶段时间预算则强制推进
        duration = interview.expected_duration or 30
        stage_time_budget_min = duration * ratio  # 该阶段分配的分钟数
        stage_time_used_min = stage_word_count / self.WORDS_PER_MINUTE
        # 允许10%的容差
        if stage_time_used_min >= stage_time_budget_min * 1.1:
            self.logger.info(
                f"Force advance by absolute time limit for interview: {interview_id}",
                extra={
                    "interview_id": str(interview_id),
                    "current_state": current_state,
                    "stage_time_used_min": round(stage_time_used_min, 1),
                    "stage_time_budget_min": round(stage_time_budget_min, 1),
                    "event": "force_advance_absolute_time",
                },
            )
            return True

        self.logger.debug(
            f"No force advance triggered for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "current_state": current_state,
                "stage_word_count": stage_word_count,
                "stage_word_limit": stage_word_limit,
                "turns": turns,
                "stage_limit": stage_limit,
                "stage_time_used_min": round(stage_time_used_min, 1),
                "stage_time_budget_min": round(stage_time_budget_min, 1),
                "event": "no_force_advance",
            },
        )
        return False

    async def _advance_state(self, interview_id: UUID) -> None:
        """推进访谈状态"""
        # 关键修复：绕过缓存直接从数据库获取，确保对象绑定到当前 session
        # 缓存中的对象可能是从已关闭的 session 中加载的 detached 对象，
        # 对当前 session 不可见，修改后 flush() 不会生成 UPDATE
        stmt = select(Interview).where(Interview.id == interview_id)
        result = await self.db.execute(stmt)
        interview = result.scalar_one_or_none()
        if not interview:
            return

        current_idx = self.STATE_FLOW.index(interview.current_state)
        if current_idx < len(self.STATE_FLOW) - 1:
            old_state = interview.current_state.value
            new_state = self.STATE_FLOW[current_idx + 1]
            from datetime import datetime
            from sqlalchemy import update as sa_update

            # 记录状态历史（使用utcnow作为转换时间，便于后续消息分界）
            history = list(interview.state_history or [])
            history.append({
                "from": old_state,
                "to": new_state.value,
                "timestamp": str(interview.updated_at),
                "transitioned_at": datetime.utcnow().isoformat(),
            })

            # 关键修复：使用 update().values() 直接执行 UPDATE，绕过 SQLAlchemy JSON 列变更检测失效问题
            # flag_modified 经日志验证未生效（第2次及以后推进时 UPDATE 语句仍缺失 state_history 列）
            stmt = (
                sa_update(Interview)
                .where(Interview.id == interview_id)
                .values(
                    current_state=new_state,
                    state_history=history,
                    updated_at=datetime.utcnow(),
                )
            )
            await self.db.execute(stmt)
            await self.db.flush()

            # 关键修复：状态推进后必须清除缓存，避免后续请求拿到旧状态
            await interview_cache.invalidate_prefix(f"interview:{interview_id}")
            await structured_content_cache.delete(f"structured:{interview_id}")

            self.logger.info(
                f"State advanced for interview: {interview_id}",
                extra={
                    "interview_id": str(interview_id),
                    "from_state": old_state,
                    "to_state": new_state.value,
                    "event": "state_advanced",
                },
            )
    
    async def complete_interview(self, interview_id: UUID) -> Dict[str, Any]:
        """完成访谈，生成最终成果（支持全套素材包一次性生成）"""
        interview = await self._get_interview_for_update(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        # 自动完成计时（若已启动）
        try:
            await self.complete_timer(interview_id)
        except ValueError:
            pass  # 计时未开始，忽略

        self.logger.info(
            f"Completing interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "current_state": interview.current_state.value,
                "event": "interview_complete_start",
            },
        )

        # 获取结构化内容
        structured = await self._get_structured_content(interview_id)

        # 确定需要生成的成果形式
        target_formats = interview.target_output_format or [OutputFormat.SCRIPT_CARD.value]
        formats_to_generate = self._resolve_output_formats(target_formats)

        # 生成成果：一次调用生成全部选中的形式
        prompt = prompt_manager.get_packaging_prompt(
            structured_content=structured,
            output_formats=formats_to_generate,
            theme=interview.theme,
        )

        system_prompt = (
            "你是一个专业的经验萃取成果封装专家。请将结构化经验转化为可直接使用的工具。\n"
            "根据要求的一次性生成全部选中的成果形式，确保各形式之间内容一致、互为补充。\n\n"
            "【强制输出格式要求】\n"
            "你必须严格按照以下JSON结构返回，顶层键为各成果形式的标识，值为对应成果内容：\n"
            "- script_card: 包含 scenario, steps(每个step必须有step/action/script/key_points/pitfalls), summary\n"
            "- checklist: 包含 title, checklist(每个category包含items，每个item有item/importance)\n"
            "- flowchart: 包含 title, nodes(每个node有id/label/type), edges(每个edge有from/to/label)\n"
            "- learning_card: 包含 title, principles(每个有title/description/scenario), tools(每个有name/description/usage), key_concepts(每个有concept/explanation)\n"
            "- case_study: 包含 title, background, challenge, process(每个有phase/description/key_decision), result, lessons\n"
            "严禁返回旧格式的 extracted_data 或扁平结构。必须返回嵌套结构。"
        )
        messages = [{"role": "user", "content": prompt}]

        raw_output = await llm_service.generate_json(system_prompt, messages, temperature=0.3)

        # 规范化输出格式（适配LLM可能返回的各种格式）
        final_output = self._normalize_final_output(raw_output, formats_to_generate, structured)

        # 更新访谈状态
        interview.current_state = InterviewState.COMPLETED
        interview.status = InterviewStatus.COMPLETED
        interview.final_output = final_output
        await self.db.flush()

        # 关键修复：完成访谈后必须清除缓存，避免后续请求拿到旧状态（final_output 为 null）
        await interview_cache.invalidate_prefix(f"interview:{interview_id}")
        await structured_content_cache.delete(f"structured:{interview_id}")

        self.logger.info(
            f"Interview completed: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "output_formats": formats_to_generate,
                "event": "interview_complete",
            },
        )
        return final_output

    def _normalize_final_output(self, raw_output: Dict[str, Any], formats_to_generate: List[str], structured: Dict[str, Any]) -> Dict[str, Any]:
        """规范化最终输出格式，适配LLM可能返回的各种格式"""
        # 情况1: 已经是正确的嵌套格式
        nested_keys = {"script_card", "checklist", "flowchart", "learning_card", "case_study"}
        if any(k in raw_output for k in nested_keys):
            return raw_output

        # 情况2: 包含 extracted_data（旧格式）
        if "extracted_data" in raw_output:
            extracted = raw_output["extracted_data"]
            return self._build_output_from_extracted(extracted, formats_to_generate, structured)

        # 情况3: 包含 output 键（中间格式）
        if "output" in raw_output and isinstance(raw_output["output"], dict):
            inner = raw_output["output"]
            # 如果 output 内部已经是嵌套格式，直接提取
            if any(k in inner for k in nested_keys):
                return inner
            return self._build_output_from_flat(inner, formats_to_generate, structured)

        # 情况4: 扁平结构，尝试适配
        return self._build_output_from_flat(raw_output, formats_to_generate, structured)

    def _build_output_from_extracted(self, extracted: Dict[str, Any], formats: List[str], structured: Dict[str, Any]) -> Dict[str, Any]:
        """从旧 extracted_data 格式构建嵌套输出"""
        output = {}
        steps = extracted.get("key_actions", []) or structured.get("steps", [])
        tools = extracted.get("tools", []) or structured.get("tools", [])
        obstacles = extracted.get("obstacles", []) or structured.get("risks", [])
        event_desc = extracted.get("event_description", "")
        decision_logic = extracted.get("decision_logic", "")
        value = extracted.get("value_assessment", {})

        if "script_card" in formats:
            output["script_card"] = {
                "title": "萃取成果",
                "scenario": event_desc,
                "steps": [
                    {
                        "step": i + 1,
                        "action": s if isinstance(s, str) else s.get("title", s.get("action", f"步骤{i+1}")),
                        "script": s if isinstance(s, str) else s.get("script", s.get("description", "")),
                        "key_points": [s if isinstance(s, str) else s.get("description", "")],
                        "pitfalls": obstacles[i:i+1] if i < len(obstacles) else []
                    }
                    for i, s in enumerate(steps)
                ],
                "summary": decision_logic
            }

        if "checklist" in formats:
            output["checklist"] = {
                "title": "操作检查表",
                "checklist": [
                    {
                        "category": "关键步骤",
                        "items": [
                            {"item": s if isinstance(s, str) else s.get("title", s.get("action", str(s))), "importance": "高"}
                            for s in steps
                        ]
                    },
                    {
                        "category": "风险规避",
                        "items": [
                            {"item": r if isinstance(r, str) else r.get("type", r.get("description", str(r))), "importance": "高"}
                            for r in obstacles
                        ]
                    }
                ]
            }

        if "flowchart" in formats:
            nodes = [{"id": "1", "label": "开始", "type": "start"}]
            for i, s in enumerate(steps):
                label = s if isinstance(s, str) else s.get("title", s.get("action", f"步骤{i+1}"))
                nodes.append({"id": str(i+2), "label": label, "type": "process"})
            nodes.append({"id": str(len(nodes)+1), "label": "完成", "type": "end"})
            edges = [{"from": str(i), "to": str(i+1), "label": ""} for i in range(1, len(nodes))]
            output["flowchart"] = {"title": "操作流程", "nodes": nodes, "edges": edges}

        if "learning_card" in formats:
            output["learning_card"] = {
                "title": "核心知识",
                "principles": [
                    {"title": "核心原则", "description": decision_logic, "scenario": "通用场景"}
                ] if decision_logic else [
                    {"title": p.get("title", p.get("name", "原则")), "description": p.get("description", p.get("detail", "")), "scenario": p.get("application_scenario", "通用场景")}
                    for p in structured.get("principles", [])
                ],
                "tools": [
                    {"name": t if isinstance(t, str) else t.get("name", t.get("title", "工具")), "description": t if isinstance(t, str) else t.get("description", t.get("detail", "")), "usage": t if isinstance(t, str) else t.get("usage_method", t.get("usage", ""))}
                    for t in tools
                ],
                "key_concepts": [
                    {"concept": "经验价值", "explanation": f"金:{value.get('金', value.get('gold', 'N/A'))} 木:{value.get('木', value.get('wood', 'N/A'))} 水:{value.get('水', value.get('water', 'N/A'))} 火:{value.get('火', value.get('fire', 'N/A'))} 土:{value.get('土', value.get('earth', 'N/A'))}"}
                ] if value else []
            }

        if "case_study" in formats:
            output["case_study"] = {
                "title": "案例复盘",
                "background": event_desc,
                "challenge": obstacles[0] if isinstance(obstacles[0], str) else obstacles[0].get("type", obstacles[0].get("description", "")) if obstacles else "",
                "process": [
                    {"phase": s if isinstance(s, str) else s.get("title", s.get("action", f"阶段{i+1}")), "description": s if isinstance(s, str) else s.get("description", s.get("detail", "")), "key_decision": ""}
                    for i, s in enumerate(steps)
                ],
                "result": decision_logic,
                "lessons": [decision_logic] if decision_logic else []
            }

        return output

    def _build_output_from_flat(self, flat: Dict[str, Any], formats: List[str], structured: Dict[str, Any]) -> Dict[str, Any]:
        """从扁平结构构建嵌套输出"""
        # 提取关键字段
        title = flat.get("title", flat.get("theme", "萃取成果"))
        scenario = flat.get("scenario", flat.get("event_description", flat.get("background", "")))
        steps_raw = flat.get("steps", flat.get("key_actions", structured.get("steps", [])))
        tools_raw = flat.get("tools", flat.get("tool_list", structured.get("tools", [])))
        risks_raw = flat.get("warnings", flat.get("risks", flat.get("obstacles", flat.get("pitfalls", structured.get("risks", [])))))
        summary = flat.get("summary", flat.get("decision_logic", flat.get("result", "")))

        output = {}

        if "script_card" in formats:
            output["script_card"] = {
                "title": title,
                "scenario": scenario,
                "steps": [
                    {
                        "step": i + 1,
                        "action": s.get("title", s.get("action", s.get("name", f"步骤{i+1}"))) if isinstance(s, dict) else str(s),
                        "script": s.get("script", s.get("key_phrase", s.get("description", s.get("detail", "")))) if isinstance(s, dict) else str(s),
                        "key_points": s.get("key_points", [s.get("description", s.get("detail", ""))]) if isinstance(s, dict) else [str(s)],
                        "pitfalls": s.get("pitfalls", []) if isinstance(s, dict) else []
                    }
                    for i, s in enumerate(steps_raw)
                ] if steps_raw else [],
                "summary": summary
            }

        if "checklist" in formats:
            output["checklist"] = {
                "title": title,
                "checklist": [
                    {
                        "category": "关键步骤",
                        "items": [
                            {"item": s.get("title", s.get("action", s.get("name", str(s)))) if isinstance(s, dict) else str(s), "importance": "高"}
                            for s in steps_raw
                        ]
                    },
                    {
                        "category": "风险规避",
                        "items": [
                            {"item": r.get("type", r.get("description", r.get("name", str(r)))) if isinstance(r, dict) else str(r), "importance": "高"}
                            for r in risks_raw
                        ]
                    }
                ] if steps_raw or risks_raw else []
            }

        if "flowchart" in formats:
            nodes = [{"id": "1", "label": "开始", "type": "start"}]
            for i, s in enumerate(steps_raw):
                label = s.get("title", s.get("action", s.get("name", f"步骤{i+1}"))) if isinstance(s, dict) else str(s)
                nodes.append({"id": str(i+2), "label": label, "type": "process"})
            nodes.append({"id": str(len(nodes)+1), "label": "完成", "type": "end"})
            edges = [{"from": str(i), "to": str(i+1), "label": ""} for i in range(1, len(nodes))]
            output["flowchart"] = {"title": title, "nodes": nodes, "edges": edges}

        if "learning_card" in formats:
            principles_raw = flat.get("principles", structured.get("principles", []))
            output["learning_card"] = {
                "title": title,
                "principles": [
                    {"title": p.get("title", p.get("name", "原则")), "description": p.get("description", p.get("detail", "")), "scenario": p.get("application_scenario", p.get("scenario", "通用场景"))}
                    for p in principles_raw
                ] if principles_raw else [],
                "tools": [
                    {"name": t.get("name", t.get("title", "工具")), "description": t.get("description", t.get("detail", "")), "usage": t.get("usage", t.get("usage_method", ""))}
                    for t in tools_raw
                ] if tools_raw else [],
                "key_concepts": [
                    {"concept": "核心经验", "explanation": summary}
                ] if summary else []
            }

        if "case_study" in formats:
            output["case_study"] = {
                "title": title,
                "background": scenario,
                "challenge": risks_raw[0] if isinstance(risks_raw[0], str) else risks_raw[0].get("type", risks_raw[0].get("description", "")) if risks_raw else "",
                "process": [
                    {"phase": s.get("title", s.get("action", s.get("name", f"阶段{i+1}"))) if isinstance(s, dict) else str(s), "description": s.get("description", s.get("detail", "")) if isinstance(s, dict) else str(s), "key_decision": ""}
                    for i, s in enumerate(steps_raw)
                ] if steps_raw else [],
                "result": summary,
                "lessons": [summary] if summary else []
            }

        return output
    
    # ==================== Structured Content ====================
    
    async def _update_structured_content(self, interview_id: UUID, updates: Dict[str, Any]) -> None:
        """更新结构化内容"""
        result = await self.db.execute(
            select(StructuredContent)
            .where(StructuredContent.interview_id == interview_id)
            .order_by(desc(StructuredContent.version))
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # 合并更新
            for key in ["steps", "principles", "tools", "risks", "decisions"]:
                if key in updates and updates[key]:
                    current = getattr(existing, key) or []
                    current.extend(updates[key])
                    setattr(existing, key, current)
            existing.version += 1
        else:
            # 创建新的结构化内容
            structured = StructuredContent(
                interview_id=interview_id,
                steps=updates.get("steps", []),
                principles=updates.get("principles", []),
                tools=updates.get("tools", []),
                risks=updates.get("risks", []),
                decisions=updates.get("decisions", []),
            )
            self.db.add(structured)
        
        await self.db.flush()
        # 失效结构化内容缓存
        await structured_content_cache.delete(f"structured:{interview_id}")

    async def _get_structured_content(self, interview_id: UUID) -> Dict[str, Any]:
        """获取结构化内容（带内存缓存）"""
        cache_key = f"structured:{interview_id}"
        cached = await structured_content_cache.get(cache_key)
        if cached is not None:
            return cached

        result = await self.db.execute(
            select(StructuredContent)
            .where(StructuredContent.interview_id == interview_id)
            .order_by(desc(StructuredContent.version))
        )
        structured = result.scalar_one_or_none()

        if not structured:
            data = {"steps": [], "principles": [], "tools": [], "risks": [], "decisions": []}
            await structured_content_cache.set(cache_key, data, ttl=30.0)
            return data

        data = {
            "steps": structured.steps or [],
            "principles": structured.principles or [],
            "tools": structured.tools or [],
            "risks": structured.risks or [],
            "decisions": structured.decisions or [],
        }
        await structured_content_cache.set(cache_key, data, ttl=30.0)
        return data
    
    async def get_structured_content_response(self, interview_id: UUID) -> Dict[str, Any]:
        """获取结构化内容（对外接口）"""
        return await self._get_structured_content(interview_id)

    # ==================== Report Generation ====================

    async def generate_report(self, interview_id: UUID, depth: str = "standard") -> Dict[str, Any]:
        """生成经验分析报告（支持任意时间重新生成）"""
        interview = await self._get_interview_for_update(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        self.logger.info(
            f"Generating analysis report for interview: {interview_id}, depth={depth}",
            extra={
                "interview_id": str(interview_id),
                "depth": depth,
                "event": "report_generate_start",
            },
        )

        # 获取完整消息历史
        messages = await self.get_messages(interview_id, limit=200)
        message_dicts = [
            {
                "role": msg.role,
                "content": msg.content,
                "message_type": msg.message_type,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ]

        # 获取结构化内容
        structured = await self._get_structured_content(interview_id)

        # 获取最终成果
        final_output = interview.final_output or {}

        # 调用报告服务生成报告
        report = await report_service.generate_report(
            theme=interview.theme,
            background=interview.background or "",
            expert_role=interview.expert_role or "",
            messages=message_dicts,
            structured_content=structured,
            final_output=final_output,
            blueprint=interview.blueprint or {},
            value_assessment=interview.value_assessment or {},
            expert_profile=interview.expert_profile or {},
            depth=depth,
        )

        # 将报告保存到 final_output 中（支持多深度版本）
        if "analysis_reports" not in final_output:
            final_output["analysis_reports"] = {}
        
        # 数据迁移：如果旧数据只有 analysis_report 且 analysis_reports 为空，
        # 将旧报告迁移到 analysis_reports 中，避免旧版本在生成新版本后丢失
        if not final_output["analysis_reports"] and final_output.get("analysis_report"):
            old_report = final_output["analysis_report"]
            old_depth = old_report.get("metadata", {}).get("depth", "standard")
            final_output["analysis_reports"][old_depth] = old_report
        
        final_output["analysis_reports"][depth] = report
        # 同时保存当前版本到 analysis_report（保持兼容）
        final_output["analysis_report"] = report

        # 关键修复：使用 update().values() 直接执行 UPDATE，绕过 SQLAlchemy JSON 列变更检测失效问题
        from sqlalchemy import update as sa_update
        await self.db.execute(
            sa_update(Interview)
            .where(Interview.id == interview_id)
            .values(final_output=final_output)
        )
        await self.db.flush()

        # 清除缓存
        await interview_cache.invalidate_prefix(f"interview:{interview_id}")

        self.logger.info(
            f"Analysis report generated for interview: {interview_id}",
            extra={
                "interview_id": str(interview_id),
                "depth": depth,
                "event": "report_generate_complete",
            },
        )

        return report

    async def get_report(self, interview_id: UUID, depth: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取已生成的报告（支持按深度获取）
        
        - 指定了 depth 且 analysis_reports 中存在：返回对应深度报告
        - 指定了 depth 但 analysis_reports 中不存在：
          - 若旧数据只有 analysis_report 且其 depth 匹配，则返回（兼容旧数据）
          - 否则返回 None（触发 404，前端进入空状态）
        - 未指定 depth：回退到当前活跃报告 analysis_report（兼容旧数据初始加载）
        """
        interview = await self.get_interview(interview_id)
        if not interview or not interview.final_output:
            return None
        final_output = interview.final_output
        if depth:
            reports = final_output.get("analysis_reports", {})
            if depth in reports:
                return reports[depth]
            # 兼容旧数据：如果 analysis_reports 为空，但 analysis_report 的深度匹配请求
            active_report = final_output.get("analysis_report")
            if active_report and not reports:
                report_depth = active_report.get("metadata", {}).get("depth")
                if report_depth == depth:
                    return active_report
            # 指定了深度但该深度确实不存在：返回 None，让前端显示空状态
            return None
        # 未指定深度：回退到当前活跃报告（兼容旧数据初始加载）
        return final_output.get("analysis_report")

    # ==================== Timer Management ====================

    async def start_timer(self, interview_id: UUID) -> Dict[str, Any]:
        """开始计时，记录 started 事件到 state_history"""
        interview = await self._get_interview_for_update(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        history = list(interview.state_history or [])

        # 检查是否已经开始过
        for h in history:
            if h.get("event_type") == "timing" and h.get("action") == "started":
                raise ValueError("Timer already started")

        from datetime import datetime
        history.append({
            "event_type": "timing",
            "action": "started",
            "at": datetime.utcnow().isoformat(),
        })

        from sqlalchemy import update as sa_update
        await self.db.execute(
            sa_update(Interview)
            .where(Interview.id == interview_id)
            .values(state_history=history)
        )
        await self.db.flush()

        self.logger.info(
            f"Timer started for interview: {interview_id}",
            extra={"interview_id": str(interview_id), "event": "timer_started"},
        )
        return {"status": "running", "elapsed_seconds": 0}

    async def pause_timer(self, interview_id: UUID) -> Dict[str, Any]:
        """暂停计时，记录 paused 事件并累加已用时长"""
        interview = await self._get_interview_for_update(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        elapsed = self._calculate_elapsed_seconds(interview)

        from datetime import datetime
        history = list(interview.state_history or [])
        history.append({
            "event_type": "timing",
            "action": "paused",
            "at": datetime.utcnow().isoformat(),
            "elapsed_seconds": elapsed,
        })

        from sqlalchemy import update as sa_update
        await self.db.execute(
            sa_update(Interview)
            .where(Interview.id == interview_id)
            .values(state_history=history)
        )
        await self.db.flush()

        self.logger.info(
            f"Timer paused for interview: {interview_id}, elapsed={elapsed}s",
            extra={
                "interview_id": str(interview_id),
                "elapsed_seconds": elapsed,
                "event": "timer_paused",
            },
        )
        return {"status": "paused", "elapsed_seconds": elapsed}

    async def resume_timer(self, interview_id: UUID) -> Dict[str, Any]:
        """恢复计时，记录 resumed 事件"""
        interview = await self._get_interview_for_update(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        from datetime import datetime
        history = list(interview.state_history or [])
        history.append({
            "event_type": "timing",
            "action": "resumed",
            "at": datetime.utcnow().isoformat(),
        })

        from sqlalchemy import update as sa_update
        await self.db.execute(
            sa_update(Interview)
            .where(Interview.id == interview_id)
            .values(state_history=history)
        )
        await self.db.flush()

        elapsed = self._calculate_elapsed_seconds(interview)
        self.logger.info(
            f"Timer resumed for interview: {interview_id}, elapsed={elapsed}s",
            extra={
                "interview_id": str(interview_id),
                "elapsed_seconds": elapsed,
                "event": "timer_resumed",
            },
        )
        return {"status": "running", "elapsed_seconds": elapsed}

    async def complete_timer(self, interview_id: UUID) -> Dict[str, Any]:
        """完成计时，记录 completed 事件并写入 final_output"""
        interview = await self._get_interview_for_update(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        elapsed = self._calculate_elapsed_seconds(interview)

        from datetime import datetime
        history = list(interview.state_history or [])
        history.append({
            "event_type": "timing",
            "action": "completed",
            "at": datetime.utcnow().isoformat(),
            "total_seconds": elapsed,
        })

        # 组装计时统计写入 final_output
        final_output = dict(interview.final_output or {})
        started_at = None
        for h in history:
            if h.get("event_type") == "timing" and h.get("action") == "started":
                started_at = h.get("at")
                break

        final_output["timer_stats"] = {
            "started_at": started_at,
            "completed_at": datetime.utcnow().isoformat(),
            "total_seconds": elapsed,
        }

        from sqlalchemy import update as sa_update
        await self.db.execute(
            sa_update(Interview)
            .where(Interview.id == interview_id)
            .values(state_history=history, final_output=final_output)
        )
        await self.db.flush()

        self.logger.info(
            f"Timer completed for interview: {interview_id}, total={elapsed}s",
            extra={
                "interview_id": str(interview_id),
                "total_seconds": elapsed,
                "event": "timer_completed",
            },
        )
        return {"status": "completed", "total_seconds": elapsed}

    async def get_timer_status(self, interview_id: UUID) -> Dict[str, Any]:
        """获取当前计时状态"""
        interview = await self.get_interview(interview_id)
        if not interview:
            raise ValueError("Interview not found")

        elapsed = self._calculate_elapsed_seconds(interview)
        state = self._get_timer_running_state(interview)

        return {"status": state, "elapsed_seconds": elapsed}

    def _calculate_elapsed_seconds(self, interview: Interview) -> int:
        """根据 state_history 中的 timing 事件计算累计已用秒数"""
        history = interview.state_history or []
        timing_events = [h for h in history if h.get("event_type") == "timing"]
        if not timing_events:
            return 0

        total = 0
        last_started_at = None

        for event in timing_events:
            action = event.get("action")
            at_str = event.get("at", "")

            if action == "started":
                last_started_at = at_str
            elif action == "paused":
                # 优先使用事件自带的 elapsed_seconds（最精确）
                if "elapsed_seconds" in event:
                    total = event["elapsed_seconds"]
                elif last_started_at:
                    try:
                        from datetime import datetime
                        start_dt = datetime.fromisoformat(last_started_at.replace("Z", "+00:00"))
                        pause_dt = datetime.fromisoformat(at_str.replace("Z", "+00:00"))
                        diff = (pause_dt - start_dt).total_seconds()
                        if diff > 0:
                            total += int(diff)
                    except (ValueError, TypeError):
                        pass
                last_started_at = None
            elif action == "resumed":
                last_started_at = at_str
            elif action == "completed":
                if "total_seconds" in event:
                    return event["total_seconds"]
                if last_started_at:
                    try:
                        from datetime import datetime
                        start_dt = datetime.fromisoformat(last_started_at.replace("Z", "+00:00"))
                        complete_dt = datetime.fromisoformat(at_str.replace("Z", "+00:00"))
                        diff = (complete_dt - start_dt).total_seconds()
                        if diff > 0:
                            total += int(diff)
                    except (ValueError, TypeError):
                        pass
                last_started_at = None

        # 若当前仍在运行，累加从 last_started_at 到此刻的时长
        if last_started_at:
            try:
                from datetime import datetime
                start_dt = datetime.fromisoformat(last_started_at.replace("Z", "+00:00"))
                now_dt = datetime.utcnow()
                # 统一时区处理
                if start_dt.tzinfo:
                    now_dt = now_dt.replace(tzinfo=start_dt.tzinfo)
                diff = (now_dt - start_dt).total_seconds()
                if diff > 0:
                    total += int(diff)
            except (ValueError, TypeError):
                pass

        return max(0, total)

    def _get_timer_running_state(self, interview: Interview) -> str:
        """获取计时器当前运行状态"""
        history = interview.state_history or []
        timing_events = [h for h in history if h.get("event_type") == "timing"]
        if not timing_events:
            return "stopped"

        last_action = timing_events[-1].get("action")
        if last_action in ("started", "resumed"):
            return "running"
        elif last_action == "paused":
            return "paused"
        elif last_action == "completed":
            return "completed"
        return "stopped"
