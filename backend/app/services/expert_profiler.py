import re
import math
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ExpertProfile:
    """专家画像数据类"""
    profile_type: str          # talkative / quiet / cautious / balanced
    type_label_cn: str         # 侃侃而谈型 / 不善言辞型 / 怕说错话型 / 均衡型
    confidence: float          # 0.0 ~ 1.0
    evidence: Dict[str, Any]   # 推断依据
    adaptation_strategy: str   # 适配策略描述
    suggestion: str            # 给AI的即时行动建议


class ExpertProfiler:
    """专家画像与沟通适配引擎

    基于专家的历史回答文本特征，实时推断其沟通风格，并生成适配策略。
    纯规则计算，不调用LLM，亚毫秒级完成。
    """

    # 确定性词汇（高确定性 = 侃侃而谈型信号）
    CERTAIN_WORDS = [
        "一定", "必须", "肯定", "绝对", "毫无疑问", "必然", "百分百",
        "肯定能", "绝对要", "务必", "决不允许", "没得商量",
    ]

    # 不确定性词汇（高频率 = 怕说错话型信号）
    UNCERTAIN_WORDS = [
        "可能", "大概", "也许", "差不多", "应该", "似乎", "感觉",
        "我觉得", "好像是", "不太确定", "也许吧", "不好说",
        "仅供参考", "个人看法", "不一定对",
    ]

    # 语气词/犹豫词（高频 = 不善言辞型或怕说错话型）
    HESITATION_WORDS = [
        "嗯", "呃", "那个", "这个", "就是", "然后", "的话",
        "怎么说呢", "其实", "其实吧", "怎么说呢",
    ]

    # 自我贬低/谦虚表达（怕说错话型信号）
    SELF_DEPRECATING = [
        "我也不太清楚", "我说不好", "我不是很专业", "可能是我理解错了",
        "这只是我的粗浅理解", "不一定准确", "仅供参考",
    ]

    # 跑题信号词（泛泛而谈型）
    OFF_TOPIC_MARKERS = [
        "另外", "顺便", "再说", "还有就是", "除此之外",
    ]

    # 类型阈值配置
    TYPE_THRESHOLDS = {
        "talkative": {
            "min_avg_length": 80,
            "min_certainty_ratio": 0.08,
            "max_uncertain_ratio": 0.05,
        },
        "quiet": {
            "max_avg_length": 60,
            "min_hesitation_ratio": 0.04,
        },
        "cautious": {
            "min_uncertain_ratio": 0.06,
            "min_self_deprecating": 1,
        },
    }

    def __init__(self):
        pass

    def analyze(self, user_messages: List[str]) -> ExpertProfile:
        """基于历史用户消息推断专家沟通风格

        Args:
            user_messages: 用户在本次访谈中的所有回答文本列表（按时间顺序）

        Returns:
            ExpertProfile: 专家画像对象
        """
        if not user_messages:
            return self._default_profile()

        features = self._extract_features(user_messages)
        profile_type, confidence, evidence = self._classify(features)

        # 生成适配策略
        strategy, suggestion = self._generate_adaptation(profile_type, features)

        type_label_map = {
            "talkative": "侃侃而谈型",
            "quiet": "不善言辞型",
            "cautious": "怕说错话型",
            "balanced": "均衡型",
        }

        return ExpertProfile(
            profile_type=profile_type,
            type_label_cn=type_label_map.get(profile_type, "未识别"),
            confidence=round(confidence, 2),
            evidence=evidence,
            adaptation_strategy=strategy,
            suggestion=suggestion,
        )

    def _extract_features(self, messages: List[str]) -> Dict[str, Any]:
        """提取回答特征向量"""
        total_chars = sum(len(m) for m in messages)
        avg_length = total_chars / len(messages) if messages else 0

        # 方差
        if len(messages) > 1:
            variance = sum((len(m) - avg_length) ** 2 for m in messages) / len(messages)
            std_dev = math.sqrt(variance)
        else:
            std_dev = 0

        all_text = "\n".join(messages)
        total_words = max(len(all_text), 1)

        # 各类词汇计数
        certain_count = sum(all_text.count(w) for w in self.CERTAIN_WORDS)
        uncertain_count = sum(all_text.count(w) for w in self.UNCERTAIN_WORDS)
        hesitation_count = sum(all_text.count(w) for w in self.HESITATION_WORDS)
        self_dep_count = sum(1 for p in self.SELF_DEPRECATING if p in all_text)

        # 比例
        certain_ratio = certain_count / total_words * 100
        uncertain_ratio = uncertain_count / total_words * 100
        hesitation_ratio = hesitation_count / total_words * 100

        # 段落数（换行分隔）
        paragraph_count = sum(len(m.split("\n")) for m in messages)
        avg_paragraphs = paragraph_count / len(messages) if messages else 0

        # 回复速率指标：最近一条相比平均长度的变化
        recent_length_ratio = len(messages[-1]) / avg_length if avg_length > 0 else 1.0

        return {
            "message_count": len(messages),
            "avg_length": round(avg_length, 1),
            "std_dev": round(std_dev, 1),
            "total_chars": total_chars,
            "certain_count": certain_count,
            "uncertain_count": uncertain_count,
            "hesitation_count": hesitation_count,
            "self_deprecating_count": self_dep_count,
            "certain_ratio": round(certain_ratio, 3),
            "uncertain_ratio": round(uncertain_ratio, 3),
            "hesitation_ratio": round(hesitation_ratio, 3),
            "avg_paragraphs": round(avg_paragraphs, 1),
            "recent_length_ratio": round(recent_length_ratio, 2),
        }

    def _classify(self, features: Dict[str, Any]) -> tuple:
        """根据特征分类专家类型并计算置信度"""
        scores = {"talkative": 0.0, "quiet": 0.0, "cautious": 0.0, "balanced": 0.0}
        evidence = {}

        avg_length = features["avg_length"]
        certain_ratio = features["certain_ratio"]
        uncertain_ratio = features["uncertain_ratio"]
        hesitation_ratio = features["hesitation_ratio"]
        self_dep = features["self_deprecating_count"]
        std_dev = features["std_dev"]

        # --- 侃侃而谈型评分 ---
        talkative_score = 0.0
        talkative_evidence = []
        if avg_length >= 120:
            talkative_score += 0.35
            talkative_evidence.append(f"平均回答长度{avg_length}字，远超常规")
        elif avg_length >= 80:
            talkative_score += 0.20
            talkative_evidence.append(f"平均回答长度{avg_length}字，偏长")
        if certain_ratio >= 0.10:
            talkative_score += 0.25
            talkative_evidence.append(f"确定性词汇占比{certain_ratio}%，表达强势")
        if uncertain_ratio <= 0.03:
            talkative_score += 0.15
            talkative_evidence.append("极少使用不确定性表达")
        if std_dev >= 60:
            talkative_score += 0.10
            talkative_evidence.append("回答长度波动大，有时展开过多")
        # 内容跑题信号：长回答+高方差
        if avg_length > 100 and features["recent_length_ratio"] > 1.5:
            talkative_score += 0.15
            talkative_evidence.append("最近回答显著加长，可能开始发散")
        scores["talkative"] = min(talkative_score, 0.95)
        evidence["talkative"] = talkative_evidence

        # --- 不善言辞型评分 ---
        quiet_score = 0.0
        quiet_evidence = []
        if avg_length <= 40:
            quiet_score += 0.40
            quiet_evidence.append(f"平均回答仅{avg_length}字，非常简短")
        elif avg_length <= 60:
            quiet_score += 0.25
            quiet_evidence.append(f"平均回答{avg_length}字，偏短")
        if hesitation_ratio >= 0.06:
            quiet_score += 0.25
            quiet_evidence.append(f"语气词/犹豫表达占比{hesitation_ratio}%，表达迟疑")
        elif hesitation_ratio >= 0.03:
            quiet_score += 0.15
            quiet_evidence.append("有一定犹豫表达")
        if avg_length <= 60 and features["avg_paragraphs"] <= 1.5:
            quiet_score += 0.15
            quiet_evidence.append("回答简短且缺乏结构化分段")
        scores["quiet"] = min(quiet_score, 0.95)
        evidence["quiet"] = quiet_evidence

        # --- 怕说错话型评分 ---
        cautious_score = 0.0
        cautious_evidence = []
        if uncertain_ratio >= 0.08:
            cautious_score += 0.35
            cautious_evidence.append(f"不确定性词汇占比{uncertain_ratio}%，频繁使用模糊表达")
        elif uncertain_ratio >= 0.05:
            cautious_score += 0.20
            cautious_evidence.append("使用较多模糊表达")
        if self_dep >= 2:
            cautious_score += 0.30
            cautious_evidence.append(f"出现{self_dep}次自我贬低/谦虚表达")
        elif self_dep >= 1:
            cautious_score += 0.15
            cautious_evidence.append("出现自我贬低表达")
        if avg_length > 80 and uncertain_ratio > 0.04:
            cautious_score += 0.10
            cautious_evidence.append("回答较长但充满不确定修饰")
        scores["cautious"] = min(cautious_score, 0.95)
        evidence["cautious"] = cautious_evidence

        # --- 均衡型（默认 fallback）---
        # 如果所有类型分数都低，则归为均衡型
        max_other = max(scores["talkative"], scores["quiet"], scores["cautious"])
        if max_other < 0.35:
            scores["balanced"] = 0.5 + (0.35 - max_other)
            evidence["balanced"] = ["各类特征均不显著，沟通风格较为均衡"]
        else:
            scores["balanced"] = max(0.0, 0.3 - max_other)
            evidence["balanced"] = []

        # 选择最高分的类型
        profile_type = max(scores, key=scores.get)
        confidence = scores[profile_type]

        # 如果最高分和次高分差距很小，降低置信度
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] - sorted_scores[1] < 0.15:
            confidence *= 0.7

        return profile_type, confidence, evidence

    def _generate_adaptation(self, profile_type: str, features: Dict[str, Any]) -> tuple:
        """生成适配策略和行动建议"""
        strategies = {
            "talkative": (
                "专家倾向于详细展开，表达自信。需要加强结构化边界提醒，适时总结确认，防止跑题。",
                "使用确认性问题帮助专家聚焦当前步骤核心；当回答过长时，礼貌打断并拉回主题：'您刚才分享的XX部分非常详细，我们先聚焦回当前步骤的核心操作，您看可以吗？'"
            ),
            "quiet": (
                "专家回答简短，可能需要更多引导和安全感。使用更具体、更小的引导性问题，降低回答门槛。",
                "将大问题拆解为小问题，一次只问一个具体动作；多用鼓励性语言：'这个细节很有价值'、'您的经验对新手非常有帮助'；允许简短回答，逐步建立信心。"
            ),
            "cautious": (
                "专家谨慎谦虚，担心说错。需要反复重申保密性和非评判立场，给予充分安全感。",
                "明确告知'没有标准答案，我们只记录真实经验'；避免质疑性追问，多用'您当时是怎么考虑的'代替'为什么这么做'；对不确定的表达给予确认和肯定。"
            ),
            "balanced": (
                "专家沟通风格均衡，回答质量良好。保持标准提问策略即可，适时根据内容调整深度。",
                "维持当前策略，根据回答内容的质量动态调整追问深度。如回答空泛则深入挖掘，如回答详细则确认并推进。"
            ),
        }
        return strategies.get(profile_type, strategies["balanced"])

    def _default_profile(self) -> ExpertProfile:
        """默认画像（样本不足时使用）"""
        return ExpertProfile(
            profile_type="balanced",
            type_label_cn="未识别（样本不足）",
            confidence=0.0,
            evidence={"note": "用户回答样本不足（少于3轮），暂无法准确判断沟通风格。使用标准策略。"},
            adaptation_strategy="样本不足，使用标准策略。",
            suggestion="保持标准提问节奏，待收集更多回答后再进行风格适配。",
        )

    def to_dict(self, profile: ExpertProfile) -> Dict[str, Any]:
        """将画像对象转为字典（用于JSON序列化）"""
        return {
            "profile_type": profile.profile_type,
            "type_label_cn": profile.type_label_cn,
            "confidence": profile.confidence,
            "evidence": profile.evidence,
            "adaptation_strategy": profile.adaptation_strategy,
            "suggestion": profile.suggestion,
        }


# 全局实例
expert_profiler = ExpertProfiler()
