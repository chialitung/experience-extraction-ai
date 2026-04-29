import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class RiskMarkerResult:
    """风险标引结果"""
    risks_found: List[Dict[str, str]]
    risk_count: int
    risk_keywords_hit: List[str]
    risk_level: str  # high / medium / low


class RiskMarker:
    """风险点自动标引引擎

    采用"规则引擎 + 模式匹配"双保险，从专家回答中自动识别并标引风险点。
    纯规则计算，不调用LLM，作为LLM提取的补充和兜底。
    """

    # ===== 风险关键词库 =====

    # 高风险关键词（直接命中）
    HIGH_RISK_KEYWORDS = [
        "易错", "容易出错", "新手常犯", "最常犯的错误", "致命错误",
        "千万不能", "绝对不要", "切忌", "切忌不要", "必须避免",
        "踩坑", "踩过的坑", "掉坑", "入坑",
        "翻车", "搞砸", "搞砸过", "失败案例",
    ]

    # 中风险关键词（需要上下文验证）
    MEDIUM_RISK_KEYWORDS = [
        "难点", "困难", "棘手", "麻烦", "困扰", "头疼",
        "容易忽视", "容易忽略", "容易漏掉", "容易忘记",
        "注意", "要注意", "特别注意", "留意", "警惕",
        "陷阱", "误区", "误解", "误操作", "误用",
        "风险", "隐患", "漏洞", "盲区", "死角",
    ]

    # 低风险关键词（提示性）
    LOW_RISK_KEYWORDS = [
        "建议", "最好", "尽量", "推荐", "不妨",
        "如果", "万一", "假设", "可能出问题",
    ]

    # 风险句式模式（正则）
    RISK_PATTERNS = [
        # "不要/避免/切忌 + 动作"
        re.compile(r"(?:不要|避免|切忌|禁止|千万别|千万别|千万别)\s*([^。，；！?.]{3,30})"),
        # "容易 + 动词"
        re.compile(r"(?:容易|极易|很容易)\s*([出犯忽忘漏错弄丢]{1,2}[^。，；！?.]{2,25})"),
        # "新手/刚开始 + 经常/容易"
        re.compile(r"(?:新手|刚开始|入门时|初学者)\s*(?:经常|容易|往往|总是|常会)\s*([^。，；！?.]{3,30})"),
        # "如果 + 条件 + 就/会 + 负面结果"
        re.compile(r"如果[^。，；！?.]{2,20}(?:就|会|可能|容易)[^。，；！?.]{2,20}(?:错|失败|问题|麻烦|损失|投诉|流失|退单)"),
        # "关键是/最重要的是 + 注意事项"
        re.compile(r"(?:关键是|最重要的是|核心在于|重点在于|难点在于)\s*([^。，；！?.]{3,40})"),
    ]

    # 去重用的归一化映射
    NORMALIZATION_MAP = {
        "容易出错": "易错",
        "容易犯错误": "新手常犯",
        "容易忽视": "容易忽略",
        "容易漏掉": "容易忽视",
        "容易忘记": "容易忽视",
        "千万别": "切忌",
        "千万不要": "切忌",
        "绝对不能": "切忌",
    }

    def mark_risks(self, answer: str) -> RiskMarkerResult:
        """从回答中提取风险点

        Args:
            answer: 专家回答文本

        Returns:
            RiskMarkerResult: 风险标引结果
        """
        if not answer or len(answer.strip()) < 10:
            return RiskMarkerResult(
                risks_found=[],
                risk_count=0,
                risk_keywords_hit=[],
                risk_level="low",
            )

        text = answer.strip()
        risks: List[Dict[str, str]] = []
        keywords_hit: List[str] = []

        # 1. 关键词匹配
        for kw in self.HIGH_RISK_KEYWORDS:
            if kw in text:
                keywords_hit.append(kw)
                # 提取包含关键词的上下文句子
                context = self._extract_context(text, kw, window=40)
                risks.append({
                    "type": "high",
                    "keyword": kw,
                    "context": context,
                    "description": f"高风险：{context}",
                    "source": "keyword",
                })

        for kw in self.MEDIUM_RISK_KEYWORDS:
            if kw in text:
                keywords_hit.append(kw)
                # 避免与高风险重复
                context = self._extract_context(text, kw, window=40)
                if not self._is_duplicate(risks, context):
                    risks.append({
                        "type": "medium",
                        "keyword": kw,
                        "context": context,
                        "description": f"中风险：{context}",
                        "source": "keyword",
                    })

        # 2. 句式模式匹配
        for pattern in self.RISK_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match else ""
                match_text = str(match).strip()
                if len(match_text) < 3:
                    continue
                if not self._is_duplicate(risks, match_text):
                    risks.append({
                        "type": "medium",
                        "keyword": "句式匹配",
                        "context": match_text,
                        "description": f"风险模式：{match_text}",
                        "source": "pattern",
                    })

        # 3. 评估整体风险等级
        high_count = sum(1 for r in risks if r["type"] == "high")
        total_count = len(risks)

        if high_count >= 2 or total_count >= 4:
            risk_level = "high"
        elif high_count >= 1 or total_count >= 2:
            risk_level = "medium"
        else:
            risk_level = "low"

        # 4. 去重和归一化
        risks = self._deduplicate_and_normalize(risks)

        return RiskMarkerResult(
            risks_found=risks,
            risk_count=len(risks),
            risk_keywords_hit=list(set(keywords_hit)),
            risk_level=risk_level,
        )

    def _extract_context(self, text: str, keyword: str, window: int = 40) -> str:
        """提取关键词周围的上下文"""
        idx = text.find(keyword)
        if idx == -1:
            return ""
        start = max(0, idx - window)
        end = min(len(text), idx + len(keyword) + window)
        context = text[start:end]
        # 清理边界，尽量从句首开始
        sentence_starts = [context.find("。") + 1, context.find("，") + 1, context.find("；") + 1, 0]
        best_start = max(s for s in sentence_starts if s >= 0)
        context = context[best_start:]
        # 清理尾部
        for p in ["\n", " "]:
            context = context.strip(p)
        if len(context) > 120:
            context = context[:120] + "..."
        return context.strip()

    def _is_duplicate(self, existing_risks: List[Dict], new_context: str) -> bool:
        """检查是否已存在相似的风险点"""
        new_normalized = self._normalize_text(new_context)
        for risk in existing_risks:
            existing_normalized = self._normalize_text(risk["context"])
            # 如果重叠率超过60%，视为重复
            if self._overlap_ratio(new_normalized, existing_normalized) > 0.6:
                return True
        return False

    def _normalize_text(self, text: str) -> str:
        """文本归一化（用于去重比较）"""
        text = text.lower()
        for old, new in self.NORMALIZATION_MAP.items():
            text = text.replace(old, new)
        # 去除标点和空格
        text = re.sub(r"[\s，。；！？、\"'\"'（）()\[\]【】]", "", text)
        return text

    def _overlap_ratio(self, a: str, b: str) -> float:
        """计算两段文本的重叠率"""
        if not a or not b:
            return 0.0
        # 使用子串匹配
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        if len(longer) == 0:
            return 0.0
        # 检查 shorter 是否包含在 longer 中
        if shorter in longer:
            return len(shorter) / len(longer)
        # 否则检查公共子串比例
        common = 0
        for i in range(len(shorter)):
            for j in range(min(8, len(shorter) - i), 0, -1):
                if shorter[i:i+j] in longer:
                    common += j
                    break
        return min(1.0, common / max(len(a), len(b)))

    def _deduplicate_and_normalize(self, risks: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """去重并归一化风险点列表"""
        seen = set()
        result = []
        for risk in risks:
            key = self._normalize_text(risk["context"])
            if key not in seen and len(key) >= 4:
                seen.add(key)
                result.append(risk)
        return result

    def merge_with_llm_risks(self, rule_risks: List[Dict], llm_risks: List[Dict]) -> List[Dict]:
        """合并规则引擎和LLM提取的风险点（去重）

        当LLM已经提取了风险点时，用规则引擎的结果作为补充，
        确保没有遗漏。
        """
        merged = list(llm_risks) if llm_risks else []
        merged_contexts = {self._normalize_text(r.get("context", "")) for r in merged}

        for r in rule_risks:
            ctx = self._normalize_text(r.get("context", ""))
            if ctx not in merged_contexts and len(ctx) >= 4:
                merged.append(r)
                merged_contexts.add(ctx)

        return merged

    def to_dict(self, result: RiskMarkerResult) -> Dict[str, Any]:
        """转为字典"""
        return {
            "risks_found": result.risks_found,
            "risk_count": result.risk_count,
            "risk_keywords_hit": result.risk_keywords_hit,
            "risk_level": result.risk_level,
        }


# 全局实例
risk_marker = RiskMarker()
