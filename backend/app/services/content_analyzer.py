import re
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from collections import Counter
import math

try:
    import jieba
    import jieba.posseg as pseg
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False


@dataclass
class AnswerAnalysis:
    """回答分析结果"""
    depth: str                # detailed / moderate / vague
    depth_score: float        # 0.0 ~ 1.0
    depth_reason: str
    off_topic: bool
    off_topic_confidence: float
    off_topic_reason: str
    gaps: List[str]
    gap_reason: str


# 中文停用词表（扩展版）
_STOP_WORDS = {
    "的", "了", "和", "与", "在", "是", "为", "对", "一个",
    "我", "你", "他", "她", "它", "我们", "你们", "他们", "这", "那", "这些", "那些",
    "有", "没有", "不", "没", "也", "就", "都", "而", "及", "或", "但是", "因为", "所以",
    "然后", "接着", "最后", "首先", "如果", "虽然", "但是", "之", "着", "过", "得", "地",
    "把", "被", "让", "给", "向", "从", "到", "于", "以", "将", "比", "跟", "同",
    "什么", "谁", "哪", "哪儿", "哪里", "多少", "几", "很", "非常", "特别", "太", "挺",
    "啊", "呢", "吧", "吗", "嘛", "哦", "嗯", "哎", "哈", "啦", "呀",
}

# 阶段语义描述文本（用于计算回答与阶段目标的语义相似度）
_STEP_DESCRIPTIONS = {
    "event_review": "复盘具体案例的背景客户情况当时的情境事件经过亲身经历成功案例",
    "framework_build": "构建方法论框架核心步骤操作流程关键原则总结归纳提炼核心方法",
    "detail_mining": "深挖具体细节操作动作话术用语怎么说怎么问具体动作执行细节",
    "obstacle_identify": "识别困难问题常见错误踩坑经历失败案例注意事项避免风险",
    "tool_extract": "提炼工具模板检查表话术卡片操作文档清单口诀可复用工具",
    "confirmation": "确认复述要点核对准确性补充纠正验证理解一致性",
}

# 保留的词性：名词(n)、动词(v)、形容词(a)、区别词(b)、习用语(i)、成语(l)
_VALID_POS = {'n', 'v', 'a', 'b', 'i', 'l', 'nr', 'ns', 'nt', 'nw', 'nz'}


def _jieba_tokenize(text: str, filter_stop: bool = True, filter_pos: bool = True) -> List[str]:
    """使用 jieba 对文本进行分词，可选过滤停用词和词性。

    如果 jieba 不可用，回退到按标点拆分的简单分词。
    """
    if not text:
        return []

    if JIEBA_AVAILABLE:
        tokens = []
        for word, flag in pseg.lcut(text):
            word = word.strip()
            if len(word) < 2:
                continue
            if filter_stop and word in _STOP_WORDS:
                continue
            if filter_pos and flag[0] not in _VALID_POS:
                continue
            tokens.append(word)
        return tokens
    else:
        # 回退：按标点拆分，保留长度>=2的词
        words = []
        for w in re.split(r"[\s，、；：。！？.!?]+", text):
            w = w.strip()
            if len(w) >= 2 and (not filter_stop or w not in _STOP_WORDS):
                words.append(w)
        return words


def _jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """计算两个集合的 Jaccard 相似度：|A∩B| / |A∪B|"""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _cosine_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    """计算两组词频向量的余弦相似度"""
    if not tokens_a or not tokens_b:
        return 0.0

    counter_a = Counter(tokens_a)
    counter_b = Counter(tokens_b)

    # 构建词汇表
    vocab = set(counter_a.keys()) | set(counter_b.keys())

    # 计算点积和模长
    dot_product = sum(counter_a[w] * counter_b[w] for w in vocab)
    norm_a = math.sqrt(sum(c * c for c in counter_a.values()))
    norm_b = math.sqrt(sum(c * c for c in counter_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class ContentAnalyzer:
    """内容理解与缺口分析引擎

    对用户回答进行程序化分析：颗粒度判断、偏离检测、缺口识别。
    纯规则计算，不调用LLM，O(n)复杂度。
    支持 jieba 中文分词进行语义相似度计算（jieba 未安装时自动回退到简单分词）。
    """

    # ===== 颗粒度分析规则 =====

    # 具体动作/细节关键词（有 = 详细）
    DETAIL_MARKERS = [
        "首先", "然后", "接着", "最后", "第一步", "第二步", "第三步",
        "打开", "点击", "输入", "填写", "检查", "核对", "确认",
        "发送", "回复", "告知", "解释", "引导", "记录",
        "具体", "细节", "步骤", "流程", "操作", "动作",
        "话术", "说：", "问道", "回答", "强调", "补充",
        "花了", "用时", "大约", "左右", "分钟", "小时",
        "用了", "借助", "通过", "利用", "工具", "模板",
    ]

    # 空泛表达信号（有 = 空泛）
    VAGUE_MARKERS = [
        "按流程", "正常做", " standard", "就做了", "按部就班",
        "差不多", "反正", "一般来说", "通常", "基本上",
        "常规操作", "正常处理", "走流程", "按规矩",
        "没什么特别的", "都是那样", "很普通",
    ]

    # 量词/数字（有 = 详细）
    QUANTITY_PATTERN = re.compile(r"\d+[个位份次条件项种种类套张小时分钟天月年¥$%]")

    # ===== 偏离检测规则 =====

    # 主题偏离信号词
    OFF_TOPIC_PHRASES = [
        "另外一件事", "还有一次", "别的客户", "另一个案例",
        "说到这个", "顺便提一下", "不相关",
        "其实我想说的是", "其实还有", "反正", "扯远了",
    ]

    def __init__(self):
        # 从配置读取漂移检测阈值，允许运行时覆盖
        try:
            from app.core.config import settings
            self.drift_threshold = getattr(settings, 'TOPIC_DRIFT_THRESHOLD', 0.35)
            self.gray_lower = getattr(settings, 'TOPIC_DRIFT_GRAY_LOWER', 0.15)
            self.prompt_inject_threshold = getattr(settings, 'TOPIC_DRIFT_PROMPT_INJECT', 0.20)
            self.max_history = getattr(settings, 'TOPIC_DRIFT_MAX_HISTORY', 10)
        except Exception:
            # 配置未加载时的保守默认值（常见于测试环境直接导入）
            self.drift_threshold = 0.35
            self.gray_lower = 0.15
            self.prompt_inject_threshold = 0.20
            self.max_history = 10

        # 预分词阶段描述文本，避免每次重复计算
        self._step_desc_tokens = {}
        for step, desc in _STEP_DESCRIPTIONS.items():
            self._step_desc_tokens[step] = _jieba_tokenize(desc, filter_stop=True, filter_pos=True)

    def analyze_answer_depth(self, answer: str) -> Dict[str, Any]:
        """判断回答颗粒度

        Returns:
            dict: {depth: str, score: float, reason: str}
        """
        if not answer or len(answer.strip()) < 10:
            return {
                "depth": "vague",
                "score": 0.1,
                "reason": "回答极短，几乎没有提供有效信息。",
            }

        text = answer.strip()
        length = len(text)

        # 计算详细度指标
        detail_count = sum(1 for m in self.DETAIL_MARKERS if m in text)
        vague_count = sum(1 for m in self.VAGUE_MARKERS if m in text)
        quantity_matches = len(self.QUANTITY_PATTERN.findall(text))

        # 句子数（按标点分割）
        sentence_count = len(re.split(r"[。！？.!?]", text))

        # 步骤枚举检测（1. 2. 3. 或 一、二、三、）
        step_pattern = re.compile(r"(?:^|\n)\s*(?:\d+[.．、]|\([\d一二三四五六七八九十]+\)|[一二三四五六七八九十][、.])")
        step_count = len(step_pattern.findall(text))

        # 综合评分
        score = 0.5  # 基线

        # 长度加分
        if length >= 300:
            score += 0.15
        elif length >= 150:
            score += 0.08
        elif length <= 50:
            score -= 0.20

        # 细节词加分
        score += min(detail_count * 0.04, 0.20)

        # 量词加分
        score += min(quantity_matches * 0.05, 0.15)

        # 步骤结构加分
        score += min(step_count * 0.08, 0.20)

        # 句子数加分
        if sentence_count >= 8:
            score += 0.08
        elif sentence_count <= 2:
            score -= 0.10

        # 空泛词减分
        score -= min(vague_count * 0.06, 0.20)

        # 裁剪到 0~1
        score = max(0.0, min(1.0, score))

        # 分级
        if score >= 0.65:
            depth = "detailed"
            reason = f"回答详细（评分{score:.2f}）：包含{detail_count}个细节标记、{quantity_matches}处量化描述、{step_count}个步骤结构、{sentence_count}个句子。"
        elif score >= 0.40:
            depth = "moderate"
            reason = f"回答中等（评分{score:.2f}）：有基本内容但细节深度一般。{'包含空泛表达' if vague_count > 0 else ''}"
        else:
            depth = "vague"
            reason = f"回答空泛（评分{score:.2f}）：{'长度不足' if length < 50 else ''}{'缺乏细节标记' if detail_count == 0 else ''}{'包含空泛表达' if vague_count > 0 else ''}。需要追问具体操作细节。"

        return {
            "depth": depth,
            "score": round(score, 2),
            "reason": reason,
            "detail_count": detail_count,
            "vague_count": vague_count,
            "quantity_matches": quantity_matches,
            "step_count": step_count,
            "sentence_count": sentence_count,
            "length": length,
        }

    def _count_consecutive_drifts(self, history: Optional[List[Dict]]) -> int:
        """从最近的历史记录中统计连续漂移的轮次（仅看当前轮次之前）。"""
        if not history:
            return 0
        count = 0
        for record in reversed(history):
            if record.get("is_off_topic") or record.get("confidence", 0) >= self.drift_threshold:
                count += 1
            else:
                break
        return count

    def detect_off_topic(self, answer: str, theme: str, current_step: str,
                         history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """偏离主题检测

        判断用户回答是否偏离了当前访谈主题和步骤目标。
        支持跨轮次历史追踪：连续漂移会触发置信度升级。

        Returns:
            dict: {is_off_topic: bool, confidence: float, reason: str, consecutive_count: int}
        """
        if not answer:
            return {"is_off_topic": False, "confidence": 0.0, "reason": "空回答，无法判断。", "consecutive_count": 0}

        text = answer.strip()
        signals = []
        score = 0.0

        # 1. 显式偏离短语（强信号，封顶 0.25）
        off_topic_hits = [p for p in self.OFF_TOPIC_PHRASES if p in text]
        if off_topic_hits:
            score += min(0.25, 0.20 * len(off_topic_hits))
            signals.append(f"检测到偏离短语：{', '.join(off_topic_hits[:3])}")

        # 2. 主题语义相似度（jieba 分词 + Jaccard）
        theme_tokens = _jieba_tokenize(theme, filter_stop=True, filter_pos=True)
        answer_tokens = _jieba_tokenize(text, filter_stop=True, filter_pos=True)
        if theme_tokens:
            theme_jaccard = _jaccard_similarity(set(theme_tokens), set(answer_tokens))
            if theme_jaccard < 0.15:
                score += 0.15
                signals.append(f"主题语义相似度低（{theme_jaccard:.0%}），可能偏离主题")

        # 3. 步骤语义相似度（jieba 分词 + 余弦相似度）
        step_relevance = self._check_step_relevance(text, current_step)
        if step_relevance < 0.25:
            score += 0.15
            signals.append(f"与当前步骤'{current_step}'的语义相关度低（{step_relevance:.0%}）")

        # 裁剪基础分
        base_score = min(1.0, score)

        # 5. 跨轮次连续漂移升级（仅当当前轮次本身已判定漂移时）
        consecutive = self._count_consecutive_drifts(history)
        total_consecutive = consecutive + (1 if base_score >= self.drift_threshold else 0)
        if total_consecutive >= 2 and base_score >= self.drift_threshold:
            escalation = 0.15 if total_consecutive == 2 else 0.30
            score = min(1.0, base_score + escalation)
            signals.append(f"连续{total_consecutive}轮检测到漂移，置信度升级+{escalation:.2f}")
        else:
            score = base_score

        # 判断阈值（使用配置值，默认 0.35）
        is_off_topic = score >= self.drift_threshold

        if is_off_topic:
            reason = f"偏离置信度{score:.2f}。{'；'.join(signals)}"
        else:
            reason = f"未检测到明显偏离（置信度{score:.2f}）。{'；'.join(signals) if signals else '回答与主题和步骤目标基本吻合。'}"

        return {
            "is_off_topic": is_off_topic,
            "confidence": round(score, 2),
            "reason": reason,
            "signals": signals,
            "consecutive_count": consecutive,
        }

    def identify_gaps(self, structured: Dict[str, Any], current_step: str,
                      blueprint: Optional[Dict[str, Any]] = None) -> List[str]:
        """基于已提取内容识别信息缺口

        根据当前步骤和已收集的结构化内容，判断还缺少哪些关键信息。
        返回列表的第一项总是已萃取内容的总结，后续项为具体缺口。

        Returns:
            list: 信息缺口描述列表（首项为已萃取内容总结）
        """
        gaps = []

        steps = structured.get("steps", []) or []
        principles = structured.get("principles", []) or []
        tools = structured.get("tools", []) or []
        risks = structured.get("risks", []) or []
        decisions = structured.get("decisions", []) or []

        # ===== 第一步：总结已萃取的关键内容 =====
        summaries = []
        if steps:
            step_names = []
            for s in steps[:5]:
                if isinstance(s, dict):
                    step_names.append(s.get("title", s.get("name", s.get("action", str(s)[:20]))))
                else:
                    step_names.append(str(s)[:20])
            summaries.append(f"已提取 {len(steps)} 个关键步骤：{', '.join(step_names)}")
        if principles:
            principle_names = []
            for p in principles[:3]:
                if isinstance(p, dict):
                    principle_names.append(p.get("title", p.get("name", str(p)[:20])))
                else:
                    principle_names.append(str(p)[:20])
            summaries.append(f"已提炼 {len(principles)} 个核心原则/框架：{', '.join(principle_names)}")
        if tools:
            tool_names = []
            for t in tools[:3]:
                if isinstance(t, dict):
                    tool_names.append(t.get("name", t.get("title", str(t)[:20])))
                else:
                    tool_names.append(str(t)[:20])
            summaries.append(f"已提取 {len(tools)} 个工具/话术：{', '.join(tool_names)}")
        if risks:
            risk_count = len(risks)
            summaries.append(f"已识别 {risk_count} 个风险/误区")
        if decisions:
            decisions_count = len(decisions)
            summaries.append(f"已记录 {decisions_count} 个关键决策点")

        if summaries:
            gaps.append("【已萃取内容总结】" + "；".join(summaries))
        else:
            gaps.append("【已萃取内容总结】尚未提取到任何结构化内容")

        # ===== 第二步：按步骤判断缺口 =====
        step_gaps = {
            "event_review": [
                ("steps", steps, "尚未提取到具体案例的关键步骤"),
                ("principles", principles, "尚未提炼出核心方法论框架"),
            ],
            "framework_build": [
                ("steps", steps, "案例步骤不够完整，缺少关键动作"),
                ("principles", principles, "缺少对核心原则/框架的提炼"),
            ],
            "detail_mining": [
                ("steps", steps, "具体步骤细节不足"),
                ("tools", tools, "尚未提取专家使用的具体工具/话术"),
            ],
            "obstacle_identify": [
                ("risks", risks, "尚未识别常见误区/困难点"),
                ("decisions", decisions, "缺少关键决策点的描述"),
            ],
            "tool_extract": [
                ("tools", tools, "可复用工具/模板提取不足"),
                ("steps", steps, "步骤流程不够清晰，难以转化为工具"),
            ],
            "confirmation": [
                ("steps", steps, "核心步骤尚未确认完整"),
                ("principles", principles, "核心原则尚未确认"),
            ],
        }

        # 检查当前步骤的缺口
        checks = step_gaps.get(current_step, [])
        for field_name, field_value, gap_desc in checks:
            if not field_value or len(field_value) < 2:
                gaps.append(gap_desc)

        # 蓝图级别缺口：如果蓝图指定了关键挖掘点，检查是否覆盖
        if blueprint and isinstance(blueprint, dict):
            key_points = blueprint.get("key_questions", []) or []
            if key_points and len(steps) < len(key_points):
                gaps.append(f"蓝图预设了{len(key_points)}个关键挖掘点，目前仅提取了{len(steps)}个")

        # 通用缺口检查
        if not steps:
            gaps.append("【关键】尚未提取到任何步骤或动作信息")
        if len(steps) >= 1 and not tools:
            # 只有有步骤后才要求工具
            if current_step in ["detail_mining", "tool_extract"]:
                gaps.append("尚未提取到专家使用的具体工具、话术或模板")
        if len(steps) >= 1 and not risks:
            if current_step in ["obstacle_identify", "tool_extract", "confirmation"]:
                gaps.append("尚未识别到常见风险/误区")

        # 去重（保留顺序）
        seen = set()
        unique_gaps = []
        for g in gaps:
            if g not in seen:
                seen.add(g)
                unique_gaps.append(g)

        return unique_gaps

    def _extract_keywords(self, theme: str) -> List[str]:
        """从主题中提取关键词（使用 jieba 分词）"""
        return _jieba_tokenize(theme, filter_stop=True, filter_pos=True)

    def _check_step_relevance(self, text: str, current_step: str) -> float:
        """检查回答与当前步骤的语义相关度（0.0 ~ 1.0）

        使用 jieba 分词 + 余弦相似度，比较回答文本与阶段描述文本的语义相似度。
        """
        desc_tokens = self._step_desc_tokens.get(current_step)
        if not desc_tokens:
            return 0.5

        answer_tokens = _jieba_tokenize(text, filter_stop=True, filter_pos=True)
        if not answer_tokens:
            return 0.0

        similarity = _cosine_similarity(answer_tokens, desc_tokens)
        # 将余弦相似度（通常在 0~0.5 之间）映射到更直观的 0~1 范围
        # 使用 sigmoid-like 映射：低相似度时快速下降，高相似度时平缓
        mapped = min(1.0, similarity * 1.5)
        return mapped

    def full_analysis(self, answer: str, theme: str, current_step: str,
                      structured: Dict[str, Any],
                      blueprint: Optional[Dict[str, Any]] = None,
                      drift_history: Optional[List[Dict]] = None) -> AnswerAnalysis:
        """完整分析：一次调用获取所有分析结果"""
        depth_result = self.analyze_answer_depth(answer)
        off_topic_result = self.detect_off_topic(answer, theme, current_step, history=drift_history)
        gaps = self.identify_gaps(structured, current_step, blueprint)

        return AnswerAnalysis(
            depth=depth_result["depth"],
            depth_score=depth_result["score"],
            depth_reason=depth_result["reason"],
            off_topic=off_topic_result["is_off_topic"],
            off_topic_confidence=off_topic_result["confidence"],
            off_topic_reason=off_topic_result["reason"],
            gaps=gaps,
            gap_reason=f"基于当前步骤'{current_step}'和已提取{len(structured.get('steps', []))}个步骤判断。",
        )

    def to_dict(self, analysis: AnswerAnalysis) -> Dict[str, Any]:
        """转为字典"""
        return {
            "depth": analysis.depth,
            "depth_score": analysis.depth_score,
            "depth_reason": analysis.depth_reason,
            "off_topic": analysis.off_topic,
            "off_topic_confidence": analysis.off_topic_confidence,
            "off_topic_reason": analysis.off_topic_reason,
            "gaps": analysis.gaps,
            "gap_reason": analysis.gap_reason,
        }


# 全局实例
content_analyzer = ContentAnalyzer()
