"""
测试访谈阶段推进的三层兜底机制

覆盖：
1. _calculate_time_budget: 阶段差异化字数预算
2. _get_stage_word_count: 当前阶段用户回答字数统计
3. _should_force_advance: 三层兜底判断逻辑
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from app.services.interview_service import InterviewService
from app.models.interview import Interview, InterviewState, Message


# ============== Fixtures ==============

@pytest.fixture
def mock_db():
    """模拟数据库会话"""
    return MagicMock()


@pytest.fixture
def service(mock_db):
    """创建 InterviewService 实例"""
    return InterviewService(db=mock_db)


@pytest.fixture
def base_interview():
    """基础访谈对象"""
    interview = MagicMock(spec=Interview)
    interview.id = str(uuid4())
    interview.expected_duration = 30
    interview.current_state = InterviewState.EVENT_REVIEW
    interview.state_history = []
    interview.expert_profile = {}
    interview.blueprint = {}
    interview.theme = "测试主题"
    interview.target_output_format = ["script_card"]
    return interview


# ============== _calculate_time_budget 测试 ==============

class TestCalculateTimeBudget:
    """测试时间预算计算（含阶段差异化字数预算）"""

    def test_default_duration_30min_event_review(self, service, base_interview):
        """30分钟访谈，复盘事件阶段应分配25% = 1500字"""
        budget = service._calculate_time_budget(base_interview, 2, "event_review", 800)
        
        assert budget["total_duration_min"] == 30
        assert budget["total_word_budget"] == 6000  # 30 * 200
        assert budget["stage_word_budget"] == 1500   # 6000 * 0.25
        assert budget["stage_word_limit"] == 1500
        assert budget["current_stage_word_count"] == 800
        assert budget["remaining_words"] == 700
        assert budget["current_turns"] == 2
        
    def test_framework_build_ratio(self, service, base_interview):
        """建构框架阶段应分配20% = 1200字"""
        budget = service._calculate_time_budget(base_interview, 1, "framework_build", 500)
        
        assert budget["stage_word_budget"] == 1200  # 6000 * 0.20
        assert budget["remaining_words"] == 700
        
    def test_detail_mining_ratio(self, service, base_interview):
        """挖掘细节阶段应分配25% = 1500字"""
        budget = service._calculate_time_budget(base_interview, 3, "detail_mining", 1600)
        
        assert budget["stage_word_budget"] == 1500  # 6000 * 0.25
        assert budget["remaining_words"] == 0       # 已超过上限
        
    def test_confirmation_ratio(self, service, base_interview):
        """复述确认阶段应分配5% = 300字"""
        budget = service._calculate_time_budget(base_interview, 1, "confirmation", 100)
        
        assert budget["stage_word_budget"] == 300   # 6000 * 0.05
        assert budget["remaining_words"] == 200
        
    def test_unknown_state_fallback(self, service, base_interview):
        """未知状态回退到 1/6 平均分配"""
        budget = service._calculate_time_budget(base_interview, 1, "unknown_state", 500)
        
        assert budget["stage_word_budget"] == 1000  # 6000 / 6
        
    def test_60min_duration(self, service, base_interview):
        """60分钟访谈，总预算翻倍"""
        base_interview.expected_duration = 60
        budget = service._calculate_time_budget(base_interview, 2, "event_review", 1000)
        
        assert budget["total_word_budget"] == 12000  # 60 * 200
        assert budget["stage_word_budget"] == 3000   # 12000 * 0.25


# ============== _get_stage_word_count 测试 ==============

class TestGetStageWordCount:
    """测试当前阶段用户回答字数统计"""

    @pytest.mark.asyncio
    async def test_only_user_messages_counted(self, service, base_interview):
        """只统计 role == 'user' 的消息"""
        msg_user = MagicMock(spec=Message)
        msg_user.role = "user"
        msg_user.content = "这是用户的回答，共十五个字"
        msg_user.extra_metadata = {"state_assessment": {"current_step": "event_review"}}
        msg_user.created_at = datetime.utcnow()
        
        msg_assistant = MagicMock(spec=Message)
        msg_assistant.role = "assistant"
        msg_assistant.content = "这是AI的问题，共十二个字"
        msg_assistant.extra_metadata = {"state_assessment": {"current_step": "event_review"}}
        msg_assistant.created_at = datetime.utcnow()
        
        service.get_interview = AsyncMock(return_value=base_interview)
        service.get_messages = AsyncMock(return_value=[msg_user, msg_assistant])
        
        count = await service._get_stage_word_count(base_interview.id)
        assert count == len("这是用户的回答，共十五个字")
        
    @pytest.mark.asyncio
    async def test_cross_stage_messages_excluded(self, service, base_interview):
        """跨阶段消息不应被统计"""
        transition_time = datetime.utcnow().isoformat()
        base_interview.state_history = [{"from": "", "to": "event_review", "transitioned_at": transition_time}]
        
        msg_old = MagicMock(spec=Message)
        msg_old.role = "user"
        msg_old.content = "old"
        msg_old.extra_metadata = {}
        msg_old.created_at = datetime(2024, 1, 1)  # 早于转换时间
        
        msg_new = MagicMock(spec=Message)
        msg_new.role = "user"
        msg_new.content = "new"
        msg_new.extra_metadata = {}
        msg_new.created_at = datetime.utcnow()  # 晚于转换时间
        # 确保 msg_new 时间严格晚于 transition_time，避免微秒级相同导致被跳过
        from datetime import timedelta
        msg_new.created_at += timedelta(seconds=1)
        
        service.get_interview = AsyncMock(return_value=base_interview)
        service.get_messages = AsyncMock(return_value=[msg_old, msg_new])
        
        count = await service._get_stage_word_count(base_interview.id)
        assert count == len("new")
        
    @pytest.mark.asyncio
    async def test_state_mismatch_excluded(self, service, base_interview):
        """状态不匹配的消息不应被统计"""
        msg_match = MagicMock(spec=Message)
        msg_match.role = "user"
        msg_match.content = "match"
        msg_match.extra_metadata = {"state_assessment": {"current_step": "event_review"}}
        msg_match.created_at = datetime.utcnow()
        
        msg_mismatch = MagicMock(spec=Message)
        msg_mismatch.role = "user"
        msg_mismatch.content = "mismatch"
        msg_mismatch.extra_metadata = {"state_assessment": {"current_step": "framework_build"}}
        msg_mismatch.created_at = datetime.utcnow()
        
        service.get_interview = AsyncMock(return_value=base_interview)
        service.get_messages = AsyncMock(return_value=[msg_match, msg_mismatch])
        
        count = await service._get_stage_word_count(base_interview.id)
        assert count == len("match")
        
    @pytest.mark.asyncio
    async def test_empty_messages(self, service, base_interview):
        """空消息列表应返回0"""
        service.get_interview = AsyncMock(return_value=base_interview)
        service.get_messages = AsyncMock(return_value=[])
        
        count = await service._get_stage_word_count(base_interview.id)
        assert count == 0
        
    @pytest.mark.asyncio
    async def test_no_interview_returns_zero(self, service):
        """访谈不存在时返回0"""
        service.get_interview = AsyncMock(return_value=None)
        
        count = await service._get_stage_word_count("non-existent-id")
        assert count == 0


# ============== _should_force_advance 测试 ==============

class TestShouldForceAdvance:
    """测试三层兜底判断逻辑"""

    @pytest.mark.asyncio
    async def test_layer1_llm_recommends_advance(self, service, base_interview):
        """第1层：LLM建议推进 → 直接返回True"""
        service.get_interview = AsyncMock(return_value=base_interview)
        
        result = await service._should_force_advance(base_interview.id, {"should_advance": True})
        assert result is True
        
    @pytest.mark.asyncio
    async def test_layer1_llm_string_true(self, service, base_interview):
        """第1层：LLM返回字符串'true' → 应正确解析并返回True"""
        service.get_interview = AsyncMock(return_value=base_interview)
        
        result = await service._should_force_advance(base_interview.id, {"should_advance": "true"})
        assert result is True
        
    @pytest.mark.asyncio
    async def test_layer1_llm_string_false(self, service, base_interview):
        """第1层：LLM返回字符串'false' → 进入下一层判断"""
        service.get_interview = AsyncMock(return_value=base_interview)
        service.get_messages = AsyncMock(return_value=[])
        service._get_stage_word_count = AsyncMock(return_value=100)  # 未超字数
        service._count_turns_in_current_state = AsyncMock(return_value=1)  # 未超轮数
        service._calculate_stage_limit = MagicMock(return_value=5)

        result = await service._should_force_advance(base_interview.id, {"should_advance": "false"})
        assert result is False
        
    @pytest.mark.asyncio
    async def test_layer2_word_limit_exceeded(self, service, base_interview):
        """第2层：字数超限 → 强制推进"""
        base_interview.expected_duration = 30
        base_interview.current_state = InterviewState.EVENT_REVIEW
        
        service.get_interview = AsyncMock(return_value=base_interview)
        service._get_stage_word_count = AsyncMock(return_value=1500)  # 刚好等于上限
        service._count_turns_in_current_state = AsyncMock(return_value=2)
        
        result = await service._should_force_advance(base_interview.id, {"should_advance": False})
        assert result is True
        
    @pytest.mark.asyncio
    async def test_layer2_word_limit_not_exceeded(self, service, base_interview):
        """第2层：字数未超限 → 进入第3层判断"""
        base_interview.expected_duration = 30
        base_interview.current_state = InterviewState.CONFIRMATION  # 上限300字

        service.get_interview = AsyncMock(return_value=base_interview)
        service.get_messages = AsyncMock(return_value=[])
        service._get_stage_word_count = AsyncMock(return_value=200)  # 未超300
        service._count_turns_in_current_state = AsyncMock(return_value=2)  # 未超轮数
        service._calculate_stage_limit = MagicMock(return_value=5)

        result = await service._should_force_advance(base_interview.id, {"should_advance": False})
        assert result is False
        
    @pytest.mark.asyncio
    async def test_layer3_turn_limit_exceeded(self, service, base_interview):
        """第3层：轮数超限 → 强制推进"""
        base_interview.expected_duration = 30
        
        service.get_interview = AsyncMock(return_value=base_interview)
        service._get_stage_word_count = AsyncMock(return_value=100)  # 未超字数
        service._count_turns_in_current_state = AsyncMock(return_value=5)  # 达到MAX_TURNS_PER_STATE
        
        result = await service._should_force_advance(base_interview.id, {"should_advance": False})
        assert result is True
        
    @pytest.mark.asyncio
    async def test_layer3_turn_limit_not_exceeded(self, service, base_interview):
        """第3层：轮数未超限 → 不推进"""
        base_interview.expected_duration = 30

        service.get_interview = AsyncMock(return_value=base_interview)
        service.get_messages = AsyncMock(return_value=[])
        service._get_stage_word_count = AsyncMock(return_value=100)  # 未超字数
        service._count_turns_in_current_state = AsyncMock(return_value=2)  # 未超轮数
        service._calculate_stage_limit = MagicMock(return_value=5)

        result = await service._should_force_advance(base_interview.id, {"should_advance": False})
        assert result is False
        
    @pytest.mark.asyncio
    async def test_no_interview_returns_false(self, service):
        """访谈不存在时返回False"""
        service.get_interview = AsyncMock(return_value=None)
        
        result = await service._should_force_advance("non-existent-id", {"should_advance": False})
        assert result is False


# ============== _calculate_stage_limit 测试 ==============

class TestCalculateStageLimit:
    """测试阶段轮数上限计算"""

    def test_30min_interview(self, service, base_interview):
        """30分钟访谈的轮数上限"""
        limit = service._calculate_stage_limit(base_interview)
        # 30 / 2.5 = 12 total turns, min(36, max(12, 12)) = 12, 12/6 = 2, min(2, 5) = 2
        assert limit == 2
        
    def test_60min_interview(self, service, base_interview):
        """60分钟访谈的轮数上限"""
        base_interview.expected_duration = 60
        limit = service._calculate_stage_limit(base_interview)
        # 60 / 2.5 = 24 total turns, min(36, max(12, 24)) = 24, 24/6 = 4, min(4, MAX_TURNS_PER_STATE=3) = 3
        assert limit == 3
        
    def test_120min_interview_capped(self, service, base_interview):
        """120分钟访谈，轮数上限被MAX_TURNS_PER_STATE限制"""
        base_interview.expected_duration = 120
        limit = service._calculate_stage_limit(base_interview)
        # 120 / 2.5 = 48 total turns, min(36, max(12, 48)) = 36, 36/6 = 6, min(6, MAX_TURNS_PER_STATE=3) = 3
        assert limit == 3
        
    def test_15min_interview_minimum(self, service, base_interview):
        """15分钟访谈，至少保证12轮总轮数"""
        base_interview.expected_duration = 15
        limit = service._calculate_stage_limit(base_interview)
        # 15 / 2.5 = 6 total turns, min(36, max(12, 6)) = 12, 12/6 = 2, min(2, 5) = 2
        assert limit == 2
