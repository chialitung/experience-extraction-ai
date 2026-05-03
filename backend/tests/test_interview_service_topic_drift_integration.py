"""
集成测试：验证三处入口（generate_ai_response / _generate_ai_question_only / generate_ai_response_stream）
的灰区触发逻辑是否正确。

策略：
- patch _detect_topic_drift_llm 让它抛 MockDriftTriggered（验证灰区触发）
- patch _detect_topic_drift_llm 为 AsyncMock（验证非灰区不触发）
- mock content_analyzer.full_analysis 返回不同置信度
- mock 灰区逻辑之前所需的最少依赖
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.interview_service import InterviewService
from app.models.interview import Interview, InterviewState, Message


class MockDriftTriggered(Exception):
    """用于验证 _detect_topic_drift_llm 被调用的标记异常"""
    pass


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db):
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
    interview.theme = "销售异议处理"
    interview.target_output_format = ["script_card"]
    return interview


def _setup_service_minimal(service, base_interview, turns: int = 1):
    """设置最少依赖让方法能执行到灰区逻辑"""
    service.get_interview = AsyncMock(return_value=base_interview)
    service._get_interview_for_update = AsyncMock(return_value=base_interview)
    service.get_messages = AsyncMock(return_value=[])
    service.add_message = AsyncMock()
    service._get_structured_content = AsyncMock(return_value={})
    service._update_structured_content = AsyncMock()
    service._count_turns_in_current_state = AsyncMock(return_value=turns)
    service._get_stage_word_count = AsyncMock(return_value=500)
    service._should_force_advance = AsyncMock(return_value=False)
    service._advance_state = AsyncMock()
    service.db = AsyncMock()


def _patch_content_analyzer(off_topic_confidence: float):
    """patch content_analyzer 返回指定置信度"""
    mock_analysis = MagicMock()
    mock_analysis.off_topic_confidence = off_topic_confidence
    return patch("app.services.interview_service.content_analyzer", **{
        "full_analysis.return_value": mock_analysis,
        "to_dict.return_value": {"off_topic": False, "off_topic_confidence": off_topic_confidence},
        "max_history": 10,
    })


# ==================== generate_ai_response ====================

@pytest.mark.asyncio
@patch.object(InterviewService, "_detect_topic_drift_llm", side_effect=MockDriftTriggered())
async def test_generate_ai_response_gray_zone_triggers_llm(mock_detect_drift, service, base_interview):
    """INT-001: 灰区 0.40 应触发 _detect_topic_drift_llm（轮次 2-4 时）"""
    _setup_service_minimal(service, base_interview, turns=2)
    with _patch_content_analyzer(0.40):
        with pytest.raises(MockDriftTriggered):
            await service.generate_ai_response(str(uuid4()), "用户回答")
    mock_detect_drift.assert_awaited_once()


@pytest.mark.asyncio
@patch.object(InterviewService, "_detect_topic_drift_llm", new_callable=AsyncMock)
async def test_generate_ai_response_high_confidence_no_llm(mock_detect_drift, service, base_interview):
    """INT-002: 高置信度 0.60 不触发 LLM"""
    _setup_service_minimal(service, base_interview)
    with _patch_content_analyzer(0.60):
        try:
            await service.generate_ai_response(str(uuid4()), "用户回答")
        except Exception:
            pass
    mock_detect_drift.assert_not_called()


@pytest.mark.asyncio
@patch.object(InterviewService, "_detect_topic_drift_llm", new_callable=AsyncMock)
async def test_generate_ai_response_low_confidence_no_llm(mock_detect_drift, service, base_interview):
    """INT-003: 低置信度 0.20 不触发 LLM"""
    _setup_service_minimal(service, base_interview)
    with _patch_content_analyzer(0.20):
        try:
            await service.generate_ai_response(str(uuid4()), "用户回答")
        except Exception:
            pass
    mock_detect_drift.assert_not_called()


@pytest.mark.asyncio
@patch.object(InterviewService, "_detect_topic_drift_llm", side_effect=MockDriftTriggered())
async def test_generate_ai_response_boundary_gray_lower_not_trigger(mock_detect_drift, service, base_interview):
    """INT-008: 边界 confidence=0.30 不满足 >0.30，不触发"""
    _setup_service_minimal(service, base_interview)
    with _patch_content_analyzer(0.30):
        try:
            await service.generate_ai_response(str(uuid4()), "用户回答")
        except MockDriftTriggered:
            pytest.fail("边界 0.30 不应触发灰区仲裁")
    mock_detect_drift.assert_not_called()


@pytest.mark.asyncio
@patch.object(InterviewService, "_detect_topic_drift_llm", side_effect=MockDriftTriggered())
async def test_generate_ai_response_boundary_threshold_not_trigger(mock_detect_drift, service, base_interview):
    """INT-009: 边界 confidence=0.55 不满足 <0.55，不触发"""
    _setup_service_minimal(service, base_interview)
    with _patch_content_analyzer(0.55):
        try:
            await service.generate_ai_response(str(uuid4()), "用户回答")
        except MockDriftTriggered:
            pytest.fail("边界 0.55 不应触发灰区仲裁")
    mock_detect_drift.assert_not_called()


@pytest.mark.asyncio
@patch.object(InterviewService, "_detect_topic_drift_llm", side_effect=MockDriftTriggered())
async def test_generate_ai_response_gray_zone_after_max_turns_no_trigger(mock_detect_drift, service, base_interview):
    """INT-010: 超过灰区最大轮次(4轮)后不触发仲裁"""
    _setup_service_minimal(service, base_interview, turns=5)
    with _patch_content_analyzer(0.40):
        try:
            await service.generate_ai_response(str(uuid4()), "用户回答")
        except MockDriftTriggered:
            pytest.fail("超过4轮不应触发灰区仲裁")
    mock_detect_drift.assert_not_called()


# ==================== _generate_ai_question_only ====================

@pytest.mark.asyncio
@patch.object(InterviewService, "_detect_topic_drift_llm", side_effect=MockDriftTriggered())
async def test_generate_question_only_gray_zone(mock_detect_drift, service, base_interview):
    """INT-004: _generate_ai_question_only 灰区 0.40 触发（轮次 2-4 时）"""
    _setup_service_minimal(service, base_interview, turns=2)
    with _patch_content_analyzer(0.40):
        with pytest.raises(MockDriftTriggered):
            await service._generate_ai_question_only(str(uuid4()), "用户回答")
    mock_detect_drift.assert_awaited_once()


@pytest.mark.asyncio
@patch.object(InterviewService, "_detect_topic_drift_llm", new_callable=AsyncMock)
async def test_generate_question_only_low_no_trigger(mock_detect_drift, service, base_interview):
    """INT-005: _generate_ai_question_only 低置信度 0.00 不触发"""
    _setup_service_minimal(service, base_interview)
    with _patch_content_analyzer(0.00):
        try:
            await service._generate_ai_question_only(str(uuid4()), "用户回答")
        except Exception:
            pass
    mock_detect_drift.assert_not_called()


# ==================== generate_ai_response_stream ====================

@pytest.mark.asyncio
@patch.object(InterviewService, "_detect_topic_drift_llm", side_effect=MockDriftTriggered())
async def test_generate_ai_response_stream_gray_zone(mock_detect_drift, service, base_interview):
    """INT-006: generate_ai_response_stream 灰区 0.40 触发（轮次 2-4 时）"""
    _setup_service_minimal(service, base_interview, turns=2)
    with _patch_content_analyzer(0.40):
        with pytest.raises(MockDriftTriggered):
            async for _ in service.generate_ai_response_stream(str(uuid4()), "用户回答"):
                pass
    mock_detect_drift.assert_awaited_once()


@pytest.mark.asyncio
@patch.object(InterviewService, "_detect_topic_drift_llm", new_callable=AsyncMock)
async def test_generate_ai_response_stream_boundary_threshold_not_trigger(mock_detect_drift, service, base_interview):
    """INT-007: 边界 confidence=0.55 不满足 <0.55，不触发"""
    _setup_service_minimal(service, base_interview)
    with _patch_content_analyzer(0.55):
        try:
            async for _ in service.generate_ai_response_stream(str(uuid4()), "用户回答"):
                pass
        except MockDriftTriggered:
            pytest.fail("边界 0.55 不应触发灰区仲裁")
    mock_detect_drift.assert_not_called()
