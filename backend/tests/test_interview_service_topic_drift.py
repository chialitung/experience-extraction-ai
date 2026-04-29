"""
测试 InterviewService 主题偏离检测相关方法

覆盖：
1. _get_last_ai_question: 获取最近一条 AI 提问
2. _detect_topic_drift_llm: LLM 语义判定
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.interview_service import InterviewService
from app.models.interview import Interview, InterviewState, Message


# ============== Fixtures ==============

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db):
    return InterviewService(db=mock_db)


# ============== _get_last_ai_question 测试 ==============

class TestGetLastAiQuestion:
    """测试获取最近 AI 提问"""

    @pytest.mark.asyncio
    async def test_normal_multiple_messages(self, service):
        """IQ-001: 正常获取最近 AI 问题"""
        msg_user1 = MagicMock(spec=Message)
        msg_user1.role = "user"
        msg_user1.content = "用户回答1"

        msg_ai1 = MagicMock(spec=Message)
        msg_ai1.role = "assistant"
        msg_ai1.content = "AI问题1"

        msg_user2 = MagicMock(spec=Message)
        msg_user2.role = "user"
        msg_user2.content = "用户回答2"

        msg_ai2 = MagicMock(spec=Message)
        msg_ai2.role = "assistant"
        msg_ai2.content = "AI问题2（最近）"

        service.get_messages = AsyncMock(return_value=[msg_user1, msg_ai1, msg_user2, msg_ai2])

        result = await service._get_last_ai_question(str(uuid4()))
        assert result == "AI问题2（最近）"

    @pytest.mark.asyncio
    async def test_no_ai_messages(self, service):
        """IQ-002: 无 AI 消息时返回空字符串"""
        msg_user1 = MagicMock(spec=Message)
        msg_user1.role = "user"
        msg_user1.content = "用户回答1"

        msg_user2 = MagicMock(spec=Message)
        msg_user2.role = "user"
        msg_user2.content = "用户回答2"

        service.get_messages = AsyncMock(return_value=[msg_user1, msg_user2])

        result = await service._get_last_ai_question(str(uuid4()))
        assert result == ""

    @pytest.mark.asyncio
    async def test_ai_message_empty_content(self, service):
        """IQ-003: AI 消息 content 为空时跳过"""
        msg_ai_empty = MagicMock(spec=Message)
        msg_ai_empty.role = "assistant"
        msg_ai_empty.content = ""

        msg_ai_valid = MagicMock(spec=Message)
        msg_ai_valid.role = "assistant"
        msg_ai_valid.content = "有效问题"

        service.get_messages = AsyncMock(return_value=[msg_ai_empty, msg_ai_valid])

        result = await service._get_last_ai_question(str(uuid4()))
        assert result == "有效问题"

    @pytest.mark.asyncio
    async def test_empty_message_list(self, service):
        """IQ-004: 消息列表为空"""
        service.get_messages = AsyncMock(return_value=[])

        result = await service._get_last_ai_question(str(uuid4()))
        assert result == ""


# ============== _detect_topic_drift_llm 测试 ==============

class TestDetectTopicDriftLlm:
    """测试 LLM 语义主题偏离判定"""

    @pytest.mark.asyncio
    @patch("app.services.interview_service.llm_service")
    async def test_normal_off_topic_true(self, mock_llm, service):
        """LLM-001: 正常判定为偏离"""
        mock_llm.generate_json = AsyncMock(return_value={
            "is_off_topic": True,
            "confidence": 0.85,
            "reason": "专家开始谈论天气",
            "suggested_correction": "让我们回到主题",
        })

        result = await service._detect_topic_drift_llm(
            user_message="今天天气很好",
            theme="销售技巧",
            current_step="event_review",
            state_goal="引导专家描述典型案例",
            last_question="请描述一个你成功处理客户异议的案例",
        )

        assert result["is_off_topic"] is True
        assert result["confidence"] == pytest.approx(0.85)
        assert "【LLM语义判定】" in result["reason"]
        assert "专家开始谈论天气" in result["reason"]
        assert result["suggested_correction"] == "让我们回到主题"

        # 验证调用参数
        call_args = mock_llm.generate_json.call_args
        assert call_args.kwargs["temperature"] == 0.0
        assert call_args.kwargs["max_tokens"] == 500
        assert "销售技巧" in call_args.kwargs["messages"][0]["content"]

    @pytest.mark.asyncio
    @patch("app.services.interview_service.llm_service")
    async def test_normal_off_topic_false(self, mock_llm, service):
        """LLM-002: 正常判定为不偏离"""
        mock_llm.generate_json = AsyncMock(return_value={
            "is_off_topic": False,
            "confidence": 0.15,
            "reason": "专家在描述案例",
            "suggested_correction": "",
        })

        result = await service._detect_topic_drift_llm(
            user_message="有一次客户说价格太贵，我是这样处理的...",
            theme="销售技巧",
            current_step="event_review",
            state_goal="引导专家描述典型案例",
            last_question="请描述一个案例",
        )

        assert result["is_off_topic"] is False
        assert result["confidence"] == pytest.approx(0.15)
        assert "【LLM语义判定】" in result["reason"]

    @pytest.mark.asyncio
    @patch("app.services.interview_service.llm_service")
    async def test_missing_fields_fallback(self, mock_llm, service):
        """LLM-003: LLM 返回缺失字段，使用默认值"""
        mock_llm.generate_json = AsyncMock(return_value={})

        result = await service._detect_topic_drift_llm(
            user_message="测试",
            theme="测试主题",
            current_step="event_review",
            state_goal="测试",
            last_question="测试问题",
        )

        assert result["is_off_topic"] is False  # 默认 False
        assert result["confidence"] == pytest.approx(0.5)  # 默认 0.5
        assert "【LLM语义判定】" in result["reason"]
        assert result["suggested_correction"] == ""

    @pytest.mark.asyncio
    @patch("app.services.interview_service.llm_service")
    async def test_llm_exception_fallback(self, mock_llm, service):
        """LLM-004: LLM 调用异常，保守回退"""
        mock_llm.generate_json = AsyncMock(side_effect=RuntimeError("API 超时"))

        result = await service._detect_topic_drift_llm(
            user_message="测试",
            theme="测试主题",
            current_step="event_review",
            state_goal="测试",
            last_question="测试问题",
        )

        assert result["is_off_topic"] is False
        assert result["confidence"] == pytest.approx(0.1)
        assert "出错" in result["reason"]
        assert "保守策略" in result["reason"]
        assert result["suggested_correction"] == ""

    @pytest.mark.asyncio
    @patch("app.services.interview_service.llm_service")
    async def test_confidence_upper_bound(self, mock_llm, service):
        """LLM-005: confidence 越界（>1.0）应裁剪为 1.0"""
        mock_llm.generate_json = AsyncMock(return_value={
            "is_off_topic": True,
            "confidence": 1.5,
            "reason": "完全偏离",
        })

        result = await service._detect_topic_drift_llm(
            user_message="测试",
            theme="测试",
            current_step="event_review",
            state_goal="测试",
            last_question="测试",
        )

        assert result["confidence"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    @patch("app.services.interview_service.llm_service")
    async def test_confidence_lower_bound(self, mock_llm, service):
        """LLM-006: confidence 越界（<0.0）应裁剪为 0.0"""
        mock_llm.generate_json = AsyncMock(return_value={
            "is_off_topic": False,
            "confidence": -0.5,
            "reason": "完全相关",
        })

        result = await service._detect_topic_drift_llm(
            user_message="测试",
            theme="测试",
            current_step="event_review",
            state_goal="测试",
            last_question="测试",
        )

        assert result["confidence"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    @patch("app.services.interview_service.llm_service")
    async def test_mock_mode_behavior(self, mock_llm, service):
        """LLM-007: mock 模式下 generate_json 的行为"""
        # mock 模式下 generate_json 可能返回 {"message": "模拟响应"}
        mock_llm.generate_json = AsyncMock(return_value={"message": "模拟响应"})

        result = await service._detect_topic_drift_llm(
            user_message="测试",
            theme="测试",
            current_step="event_review",
            state_goal="测试",
            last_question="测试",
        )

        # 缺失 is_off_topic 字段，使用默认值 False
        assert result["is_off_topic"] is False
        assert result["confidence"] == pytest.approx(0.5)
        # 不崩溃即为通过
        assert "reason" in result
