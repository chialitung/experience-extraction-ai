"""
测试主题偏离检测规则引擎阈值调整（0.35→0.55）

覆盖 detect_off_topic 的阈值边界、信号组合和防御性边界。
注意：_extract_keywords 按标点分隔提取>=2字的实词，不进一步分词。
"""

import pytest
from app.services.content_analyzer import ContentAnalyzer

content_analyzer = ContentAnalyzer()


class TestDetectOffTopicThreshold:
    """测试 detect_off_topic 阈值调整后的行为变化"""

    def test_multiple_signals_triggers_drift(self):
        """CA-001: 2个偏离短语(封顶0.25) + 主题低(0.15) + 步骤低(0.15) = 0.55 >= 0.55，偏离"""
        answer = "另外一件事，还有一次，今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        assert result["is_off_topic"] is True
        assert result["confidence"] == pytest.approx(0.55, abs=0.01)
        assert "另外一件事" in result["reason"]

    def test_pure_off_topic_phrase_only(self):
        """CA-001b: 1个偏离短语(0.20) + 步骤相关度低(0.15) = 0.35 < 0.55，不偏离"""
        answer = "另外一件事，但我仍在做客户异议处理的工作。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        assert result["is_off_topic"] is False
        assert result["confidence"] == pytest.approx(0.35, abs=0.01)

    def test_low_theme_and_step_relevance_no_longer_drift(self):
        """CA-002: 主题匹配度低(0.15) + 步骤相关度低(0.15) = 0.30 < 0.55，不偏离"""
        answer = "今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        assert result["is_off_topic"] is False
        assert result["confidence"] == pytest.approx(0.30, abs=0.01)
        assert "语义相似度低" in result["reason"]
        assert "相关度低" in result["reason"]

    def test_multiple_signals_high_confidence(self):
        """CA-003: 多个信号叠加，高置信度偏离，规则直接判定不走LLM"""
        answer = "另外一件事，还有一次，今天天气很好，我去公园散步了，没有什么特别的。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        assert result["is_off_topic"] is True
        assert result["confidence"] >= 0.50
        assert len(result["signals"]) >= 2

    def test_on_topic_low_confidence(self):
        """CA-004: 正常回答，包含完整主题词组，步骤相关度略低但不触发漂移，置信度0.15"""
        answer = "有一次我遇到客户异议处理的情况，我对价格提出了异议，我当时是这样处理的..."
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        assert result["is_off_topic"] is False
        assert result["confidence"] == pytest.approx(0.15, abs=0.01)
        assert "未检测到明显偏离" in result["reason"]

    def test_empty_answer(self):
        """CA-005: 空回答，防御性边界"""
        result = content_analyzer.detect_off_topic(
            answer="",
            theme="客户异议处理",
            current_step="event_review",
        )
        assert result["is_off_topic"] is False
        assert result["confidence"] == 0.0
        assert "空回答" in result["reason"]

    def test_long_unstructured_no_extra_score(self):
        """CA-006: 超长无结构回答不再额外加分（长文本惩罚已移除）"""
        short_answer = "今天" * 100
        result_short = content_analyzer.detect_off_topic(
            answer=short_answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 主题匹配度低(0.15) + 步骤相关度低(0.15) = 0.30
        assert result_short["confidence"] == pytest.approx(0.30, abs=0.01)

        long_answer = "今天" * 201
        assert len(long_answer) > 400
        result_long = content_analyzer.detect_off_topic(
            answer=long_answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 长文本惩罚已移除，与短回答相同
        assert result_long["confidence"] == pytest.approx(0.30, abs=0.01)
        assert "疑似发散" not in result_long["reason"]

    def test_long_structured_no_extra_score(self):
        """CA-007: 超长但有清晰结构，也不增加发散分（长文本惩罚已移除）"""
        structured_answer = "\n".join([f"{i}. 今天天气很好" for i in range(1, 51)])
        assert len(structured_answer) > 400
        result = content_analyzer.detect_off_topic(
            answer=structured_answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 主题匹配度低(0.15) + 步骤相关度低(0.15) = 0.30
        assert result["confidence"] == pytest.approx(0.30, abs=0.01)

    def test_boundary_below_threshold(self):
        """CA-008: 恰好低于阈值 0.55 的边界"""
        answer = "当时我在复盘案例背景。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 主题语义匹配度低(0.15)，步骤语义相关度高(>=0.25)，无偏离短语
        # 0.15 < 0.55 → 不偏离
        assert result["is_off_topic"] is False
        assert result["confidence"] == pytest.approx(0.15, abs=0.01)

    def test_drift_confidence_below_gray_zone(self):
        """CA-009: 低于灰区下限(0.30)示例：仅步骤相关度低=0.15"""
        answer = "我去公园散步了，天气很好。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 主题匹配度低(0.15) + 步骤相关度低(0.15) = 0.30
        # 0.30 不满足 > 0.30（灰区下限），不在灰区
        assert result["confidence"] == pytest.approx(0.30, abs=0.01)
        assert result["is_off_topic"] is False

        # 仅步骤匹配，主题不匹配
        answer2 = "有一次，当时的情况很紧急，这是一个案例。"
        result2 = content_analyzer.detect_off_topic(
            answer=answer2,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 步骤全匹配(>=0.25)，主题不匹配(0.15)
        # confidence = 0.15 → 低于灰区下限 0.30
        assert result2["confidence"] == pytest.approx(0.15, abs=0.01)
        assert result2["is_off_topic"] is False

    def test_new_threshold_boundary_exactly_0_55(self):
        """CA-014: 新阈值 0.55 边界：恰好 0.55 触发偏离"""
        # 2个偏离短语(封顶0.25) + 主题低(0.15) + 步骤低(0.15) = 0.55
        answer = "另外一件事，还有一次，今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        assert result["is_off_topic"] is True
        assert result["confidence"] == pytest.approx(0.55, abs=0.01)


class TestConsecutiveDriftEscalation:
    """测试跨轮次连续漂移升级逻辑"""

    def test_consecutive_drift_escalation_2(self):
        """CA-010: 连续2轮漂移，置信度+0.15升级"""
        history = [
            {"is_off_topic": True, "confidence": 0.55},
        ]
        # 需要基础分 >= 0.55 才能触发阈值：2个偏离短语 + 主题低 + 步骤低
        answer = "另外一件事，还有一次，今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
            history=history,
        )
        # 基础分 0.55 + 连续2轮升级 0.15 = 0.70
        assert result["confidence"] == pytest.approx(0.70, abs=0.01)
        assert result["is_off_topic"] is True
        assert result["consecutive_count"] == 1
        assert "连续2轮检测到漂移" in result["reason"]

    def test_consecutive_drift_escalation_3_plus(self):
        """CA-011: 连续3轮及以上漂移，置信度+0.30升级"""
        history = [
            {"is_off_topic": True, "confidence": 0.55},
            {"is_off_topic": True, "confidence": 0.70},
        ]
        answer = "另外一件事，还有一次，今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
            history=history,
        )
        # 基础分 0.55 + 连续3轮升级 0.30 = 0.85
        assert result["confidence"] == pytest.approx(0.85, abs=0.01)
        assert result["is_off_topic"] is True
        assert result["consecutive_count"] == 2
        assert "连续3轮检测到漂移" in result["reason"]

    def test_no_escalation_after_on_topic(self):
        """CA-012: 中间有轮次不漂移，连续计数重置，不升级"""
        history = [
            {"is_off_topic": True, "confidence": 0.55},
            {"is_off_topic": False, "confidence": 0.10},  # 最近一轮不漂移，打断连续
        ]
        answer = "另外一件事，还有一次，今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
            history=history,
        )
        # 最近历史不漂移，当前虽然漂移但只有1轮连续，不触发升级
        assert result["confidence"] == pytest.approx(0.55, abs=0.01)
        assert result["consecutive_count"] == 0
        assert "连续" not in result["reason"]  # 不升级时不出现在reason中

    def test_empty_history_no_escalation(self):
        """CA-013: 空历史不触发升级"""
        answer = "另外一件事，还有一次，今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
            history=[],
        )
        assert result["confidence"] == pytest.approx(0.55, abs=0.01)
        assert result["consecutive_count"] == 0
        assert "连续" not in result["reason"]
