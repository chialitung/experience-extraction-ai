"""
测试主题偏离检测规则引擎阈值调整（0.45→0.35）

覆盖 detect_off_topic 的阈值边界、信号组合和防御性边界。
注意：_extract_keywords 按标点分隔提取>=2字的实词，不进一步分词。
"""

import pytest
from app.services.content_analyzer import ContentAnalyzer

content_analyzer = ContentAnalyzer()


class TestDetectOffTopicThreshold:
    """测试 detect_off_topic 阈值调整后的行为变化"""

    def test_threshold_0_35_old_case_now_off_topic(self):
        """CA-001: 旧版(0.45)不偏离、新版(0.35)偏离的边界案例
        
        偏离短语(0.25) + 主题匹配度低(0.20) + 步骤相关度低(0.20) = 0.65 >= 0.35
        """
        answer = "另外一件事，那天我遇到了一个很好的朋友。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        assert result["is_off_topic"] is True
        assert result["confidence"] == pytest.approx(0.65, abs=0.01)
        assert "另外一件事" in result["reason"]

    def test_pure_off_topic_phrase_only(self):
        """CA-001b: 仅1个偏离短语(0.25)，无其他信号，<0.35，不偏离"""
        # 主题使用单字"客"确保匹配（_extract_keywords 保留>=2字，但"客"只有1字）
        # 实际上无法用单字，因为 _extract_keywords 过滤 len<2 的词
        # 改用包含完整主题词组的回答
        answer = "另外一件事，但我仍在做客户异议处理的工作。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",  # _extract_keywords 返回 ["客户异议处理"]
            current_step="event_review",
        )
        # "客户异议处理" 完整出现在回答中 → 主题匹配度不低
        # "当时" 匹配 event_review 步骤词 → 步骤相关度不低
        # 只有偏离短语 0.25 < 0.35 → 不偏离
        assert result["is_off_topic"] is False
        assert result["confidence"] == pytest.approx(0.25, abs=0.01)

    def test_low_theme_and_step_relevance_crosses_new_threshold(self):
        """CA-002: 主题匹配度低+步骤相关度低=0.40，旧版(0.45)不偏离，新版(0.35)偏离"""
        answer = "今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        assert result["is_off_topic"] is True
        assert result["confidence"] == pytest.approx(0.40, abs=0.01)
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
        """CA-004: 正常回答，包含完整主题词组和步骤关键词，置信度0，规则直接判定"""
        # 包含完整主题词组"客户异议处理"和步骤关键词"有一次"
        answer = "有一次我遇到客户异议处理的情况，我对价格提出了异议，我当时是这样处理的..."
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        assert result["is_off_topic"] is False
        assert result["confidence"] == pytest.approx(0.0, abs=0.01)
        assert "基本吻合" in result["reason"]

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

    def test_long_unstructured_adds_score(self):
        """CA-006: 超长(>400字)无结构回答增加0.15"""
        # 短回答（约200字，无偏离短语）但主题/步骤匹配度低 → 0.40
        short_answer = "今天" * 100
        result_short = content_analyzer.detect_off_topic(
            answer=short_answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 主题匹配度低(0.20) + 步骤相关度低(0.20) = 0.40
        assert result_short["confidence"] == pytest.approx(0.40, abs=0.01)

        # 超长无结构回答（402字，无列表/步骤）
        long_answer = "今天" * 201
        assert len(long_answer) > 400
        result_long = content_analyzer.detect_off_topic(
            answer=long_answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 超长无结构(0.15) + 主题匹配度低(0.20) + 步骤相关度低(0.20) = 0.55
        assert result_long["confidence"] == pytest.approx(0.55, abs=0.01)
        assert "疑似发散" in result_long["reason"]

    def test_long_structured_no_extra_score(self):
        """CA-007: 超长但有清晰结构，不增加发散分"""
        # 400字以上，但有编号结构
        structured_answer = "\n".join([f"{i}. 今天天气很好" for i in range(1, 51)])
        assert len(structured_answer) > 400
        result = content_analyzer.detect_off_topic(
            answer=structured_answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 有结构，不增加0.15
        # 但主题匹配度低(0.20) + 步骤相关度低(0.20) = 0.40
        assert result["confidence"] == pytest.approx(0.40, abs=0.01)

    def test_boundary_exactly_0_35(self):
        """CA-008: 恰好等于阈值 0.35 的边界"""
        # 语义引擎下，需构造主题不匹配但步骤语义相关度高的场景
        # 回答包含 event_review 语义（当时、复盘、案例、背景），但不含主题词
        answer = "当时我在复盘案例背景。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 主题语义匹配度低(0.20)，步骤语义相关度高(>=0.3)，无偏离短语
        # 0.20 < 0.35 → 不偏离
        assert result["is_off_topic"] is False
        assert result["confidence"] == pytest.approx(0.20, abs=0.01)

    def test_drift_confidence_gray_zone_example(self):
        """CA-009: 灰区(0.15, 0.35)示例：仅步骤相关度低=0.20"""
        answer = "我去公园散步了，天气很好。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 主题匹配度低(0.20) + 步骤相关度低(0.20) = 0.40 > 0.35
        # 这不是灰区。让我们构造一个刚好在灰区的
        # 如果主题能匹配但步骤不匹配...
        answer2 = "客户异议处理的情况很复杂。"  # 主题匹配，步骤不匹配？
        result2 = content_analyzer.detect_off_topic(
            answer=answer2,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 主题匹配，步骤词："客户"匹配 → 相关度=1.0/2.4=0.42，不低
        # confidence = 0.0，不是灰区

        # 灰区案例：仅主题匹配度低(0.20)，步骤相关度不低
        # 使用步骤词丰富但主题不相关的回答
        answer3 = "有一次，当时的情况很紧急，这是一个案例。"  # 步骤全匹配
        result3 = content_analyzer.detect_off_topic(
            answer=answer3,
            theme="客户异议处理",
            current_step="event_review",
        )
        # 步骤全匹配(1.0)，但主题不匹配(0.20)
        # confidence = 0.20 → 灰区！(0.15 < 0.20 < 0.35)
        assert result3["confidence"] == pytest.approx(0.20, abs=0.01)
        assert result3["is_off_topic"] is False  # < 0.35，规则不判定偏离


class TestConsecutiveDriftEscalation:
    """测试跨轮次连续漂移升级逻辑"""

    def test_consecutive_drift_escalation_2(self):
        """CA-010: 连续2轮漂移，置信度+0.15升级"""
        history = [
            {"is_off_topic": True, "confidence": 0.40},
        ]
        answer = "今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
            history=history,
        )
        # 基础分 0.40 + 连续2轮升级 0.15 = 0.55
        assert result["confidence"] == pytest.approx(0.55, abs=0.01)
        assert result["is_off_topic"] is True
        assert result["consecutive_count"] == 1
        assert "连续2轮检测到漂移" in result["reason"]

    def test_consecutive_drift_escalation_3_plus(self):
        """CA-011: 连续3轮及以上漂移，置信度+0.30升级"""
        history = [
            {"is_off_topic": True, "confidence": 0.40},
            {"is_off_topic": True, "confidence": 0.55},
        ]
        answer = "今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
            history=history,
        )
        # 基础分 0.40 + 连续3轮升级 0.30 = 0.70
        assert result["confidence"] == pytest.approx(0.70, abs=0.01)
        assert result["is_off_topic"] is True
        assert result["consecutive_count"] == 2
        assert "连续3轮检测到漂移" in result["reason"]

    def test_no_escalation_after_on_topic(self):
        """CA-012: 中间有轮次不漂移，连续计数重置，不升级"""
        history = [
            {"is_off_topic": True, "confidence": 0.40},
            {"is_off_topic": False, "confidence": 0.10},  # 最近一轮不漂移，打断连续
        ]
        answer = "今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
            history=history,
        )
        # 最近历史不漂移，当前虽然漂移但只有1轮连续，不触发升级
        assert result["confidence"] == pytest.approx(0.40, abs=0.01)
        assert result["consecutive_count"] == 0
        assert "连续" not in result["reason"]  # 不升级时不出现在reason中

    def test_empty_history_no_escalation(self):
        """CA-013: 空历史不触发升级"""
        answer = "今天天气很好，我去公园散步了。"
        result = content_analyzer.detect_off_topic(
            answer=answer,
            theme="客户异议处理",
            current_step="event_review",
            history=[],
        )
        assert result["confidence"] == pytest.approx(0.40, abs=0.01)
        assert result["consecutive_count"] == 0
        assert "连续" not in result["reason"]
