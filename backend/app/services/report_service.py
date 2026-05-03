import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.services.llm_service import llm_service
from app.services.prompt_manager import prompt_manager
from app.core.logging import get_logger


class ReportService:
    """经验分析报告生成服务

    支持三种深度：
    - brief: 简要版（800-1200字，聚焦核心结论）
    - standard: 标准版（2000-3000字，完整分析）
    - deep: 深度版（4000-6000字，含推导过程与案例）
    """

    DEPTH_CONFIG = {
        "brief": {
            "name": "简要版",
            "word_target": "800-1200字",
            "description": "聚焦核心结论，适合快速阅读",
            "sections_required": [
                "executive_summary",
                "key_steps_analysis",
                "obstacles_and_risks",
                "application_guidance",
            ],
        },
        "standard": {
            "name": "标准版",
            "word_target": "2000-3000字",
            "description": "完整分析，适合归档与培训",
            "sections_required": [
                "executive_summary",
                "case_background",
                "methodology_framework",
                "key_steps_analysis",
                "obstacles_and_risks",
                "tools_and_scripts",
                "application_guidance",
                "value_assessment",
                "lessons_learned",
            ],
        },
        "deep": {
            "name": "深度版",
            "word_target": "4000-6000字",
            "description": "含推导过程与案例，适合研究与深度复盘",
            "sections_required": [
                "executive_summary",
                "case_background",
                "methodology_framework",
                "key_steps_analysis",
                "decision_logic_analysis",
                "obstacles_and_risks",
                "tools_and_scripts",
                "application_guidance",
                "value_assessment",
                "lessons_learned",
                "references",
            ],
        },
        "expert": {
            "name": "专家版",
            "word_target": "6000-10000字",
            "description": "完整方法论分析，含头-身-足-包四层结构、萃取层级标识、场景适配、根因链分析",
            "sections_required": [
                "executive_summary",
                "case_background",
                "four_layer_structure",
                "methodology_framework",
                "key_steps_analysis",
                "decision_logic_analysis",
                "process_obstacle_mapping",
                "root_cause_analysis",
                "tools_and_scripts",
                "application_guidance",
                "critical_success_factors",
                "value_assessment",
                "lessons_learned",
                "references",
                "three_review_assessment",
            ],
        },
    }

    def __init__(self):
        self.logger = get_logger("app.report")

    def _build_report_prompt(
        self,
        theme: str,
        background: str,
        expert_role: str,
        messages: List[Dict[str, Any]],
        structured_content: Dict[str, Any],
        final_output: Dict[str, Any],
        blueprint: Dict[str, Any],
        value_assessment: Dict[str, Any],
        expert_profile: Dict[str, Any],
        depth: str,
    ) -> str:
        """构建报告生成提示词"""
        config = self.DEPTH_CONFIG.get(depth, self.DEPTH_CONFIG["standard"])

        # 构建消息摘要
        message_summary = []
        for msg in messages:
            role_label = "专家" if msg.get("role") == "user" else "访谈者"
            content = msg.get("content", "")[:300]
            if len(msg.get("content", "")) > 300:
                content += "..."
            message_summary.append(f"[{role_label}] {content}")

        # 构建访谈数据摘要
        interview_data = {
            "theme": theme,
            "background": background or "未提供",
            "expert_role": expert_role or "未指定",
            "structured_content": structured_content,
            "final_output": final_output,
            "blueprint": blueprint,
            "value_assessment": value_assessment,
            "expert_profile": expert_profile,
            "message_count": len(messages),
        }

        prompt = f"""# 任务：生成经验分析报告

## 报告要求
- 深度级别：{config['name']}（{config['word_target']}）
- 用途：{config['description']}

## 访谈数据

### 基本信息
- 主题：{theme}
- 背景：{background or '未提供'}
- 专家角色：{expert_role or '未指定'}
- 消息总数：{len(messages)}

### 结构化萃取内容
```json
{json.dumps(structured_content, ensure_ascii=False, indent=2)}
```

### 最终成果输出
```json
{json.dumps(final_output, ensure_ascii=False, indent=2)[:3000]}
```

### 蓝图信息
```json
{json.dumps(blueprint, ensure_ascii=False, indent=2)[:2000]}
```

### 价值评估（五维：高价值、有难度、常使用、急需要、覆盖广）
```json
{json.dumps(value_assessment, ensure_ascii=False, indent=2)}
```

### 专家画像
```json
{json.dumps(expert_profile, ensure_ascii=False, indent=2)}
```

### 访谈对话摘要
{chr(10).join(message_summary[:30])}

## 输出格式要求

你必须严格按照以下JSON结构返回报告内容：

```json
{{
  "analysis_report": {{
    "executive_summary": "执行摘要（300字内）",
    "case_background": "案例背景详述",
    "methodology_framework": "方法论框架（问题定义→解决思路→关键假设）",
    "key_steps_analysis": "关键步骤详解（每一步的动作、决策逻辑、替代方案）",
    "decision_logic_analysis": "决策逻辑深度分析（仅深度版需要）",
    "obstacles_and_risks": "风险与挑战分析（按严重度排序）",
    "tools_and_scripts": "工具与话术清单",
    "application_guidance": "应用建议（适用场景、前提条件、常见变体）",
    "value_assessment": "价值评估（五维分析：高价值、有难度、常使用、急需要、覆盖广）",
    "lessons_learned": "可迁移的经验教训",
    "references": "相关概念/理论引用（仅深度版需要）"
  }},
  "metadata": {{
    "depth": "{depth}",
    "generated_at": "{datetime.utcnow().isoformat()}",
    "word_count": 0
  }}
}}
```

## 重要规则
1. 每个章节必须是完整的Markdown格式文本（支持标题、列表、表格、引用）
2. {config['name']}必须包含以下章节：{', '.join(config['sections_required'])}
3. 深度版需要在 decision_logic_analysis 中分析专家每一步的决策逻辑、信息来源、替代方案考量
4. 价值评估章节必须包含五维（高价值、有难度、常使用、急需要、覆盖广）的具体评分和解释。
5. 应用建议要具体，包含适用场景、前提条件、常见变体和注意事项
6. 所有内容必须基于访谈实际数据，不得编造
7. 字数严格控制在 {config['word_target']} 范围内
8. 输出必须是合法JSON，所有字符串值必须使用双引号
{self._build_expert_instructions(depth)}
"""
        return prompt

    def _build_expert_instructions(self, depth: str) -> str:
        """构建专家版特殊指令"""
        if depth != "expert":
            return ""
        return """

## 专家版特殊要求（必须严格执行）

### 1. 头-身-足-包四层结构
在 four_layer_structure 章节中，将所有内容按以下四层重新组织并概述：
- 【头/思维层面】核心原则、价值判断、适用边界、决策哲学
- 【身/方法层面】可复用的方法论框架、系统方法、核心流程
- 【足/行为层面】具体操作步骤、动作、行为细节、执行要点
- 【包/应用层面】配套工具、模板、检查表、使用说明、口诀

### 2. 萃取层级标识
在 key_steps_analysis 和 methodology_framework 章节中，为每个要点标注其萃取层级：
- 【一级/切框架】流程步骤/核心要素（不超过7项）
- 【二级/挖细节】关键环节/动作/要点
- 【三级/识障碍】易错点/困难点/易忽略点
- 【四级/配工具】检查表/话术/流程图/口诀
- 【五级/做优化】系统优化/三审定稿建议

### 3. SPOR框架背景描述
在 case_background 章节中，案例背景必须按 SPOR 框架组织：
- S-Situation（情境）：何时、何地、何人、何环境
- P-Problem（问题）：面临什么挑战、压力、冲突
- O-Operation（过程）：采取了什么行动、关键决策
- R-Result（结果）：取得了什么成果（必须包含量化数据）

### 4. 流程-障碍映射表
在 process_obstacle_mapping 章节中，以 Markdown 表格形式输出每个流程步骤对应的风险/障碍：
| 流程步骤 | 易错点 | 困难点 | 易忽略点 | 预防措施 |
要求：每个步骤至少对应一行，已识别的风险必须映射到具体步骤。

### 5. 5Why根因链
在 root_cause_analysis 章节中，对每个主要风险，展示完整的 5 层根因追溯链：
表面现象 → 直接原因 → 间接原因 → 深层原因 → 根因
格式要求：使用箭头链式表达，每层用一句话说明。

### 6. 关键成功因素排序
在 critical_success_factors 章节中：
- 提取 3-5 个关键成功因素
- 每个因素按五维（高价值、有难度、常使用、急需要、覆盖广）评分（1-10分）
- 按综合优先级排序（priority=1为最高）
- 说明每个因素为什么关键、在什么场景下最关键

### 7. 场景适配指导
在 application_guidance 章节中，基于访谈数据推断或引用已采集的场景变量，给出不同场景下的适配策略。格式：场景名称 → 关键变量 → 调整建议。

### 8. 三审定稿评估
在 three_review_assessment 章节中，对报告本身进行质量审核：
- 审选题：主题价值评估、与业务目标的契合度
- 审经验：严谨性（数据支撑）、完整性（四层覆盖）、逻辑性（因果清晰）、准确性（无误导）
- 审落地：易用性（工具可直接使用）、实用性（新手可复现）、传承性（可培训推广）
每个维度给出通过/待改进/不通过的判定及具体理由。"""

    async def generate_report(
        self,
        theme: str,
        background: str,
        expert_role: str,
        messages: List[Dict[str, Any]],
        structured_content: Dict[str, Any],
        final_output: Dict[str, Any],
        blueprint: Dict[str, Any],
        value_assessment: Dict[str, Any],
        expert_profile: Dict[str, Any],
        depth: str = "standard",
    ) -> Dict[str, Any]:
        """生成经验分析报告"""

        if depth not in self.DEPTH_CONFIG:
            depth = "standard"

        self.logger.info(
            f"Generating report for interview, depth={depth}",
            extra={"depth": depth, "theme": theme, "event": "report_generate_start"},
        )

        prompt = self._build_report_prompt(
            theme=theme,
            background=background,
            expert_role=expert_role,
            messages=messages,
            structured_content=structured_content,
            final_output=final_output,
            blueprint=blueprint,
            value_assessment=value_assessment,
            expert_profile=expert_profile,
            depth=depth,
        )

        system_prompt = (
            "你是一位资深的企业知识管理顾问和经验萃取专家。"
            "你的任务是基于访谈数据生成一份专业的经验分析报告。"
            "报告要求逻辑清晰、分析深入、语言专业、可操作性强。"
            "所有分析必须基于访谈实际数据，不得编造。"
        )

        messages_prompt = [{"role": "user", "content": prompt}]

        # 根据深度级别设置 max_tokens：brief 3000, standard 6000, deep 10000, expert 15000
        max_tokens_map = {"brief": 3000, "standard": 6000, "deep": 10000, "expert": 15000}
        max_tokens = max_tokens_map.get(depth, 6000)

        try:
            response = await llm_service.generate_json(
                system_prompt, messages_prompt, temperature=0.3, max_tokens=max_tokens
            )

            report_data = response.get("analysis_report", {})
            metadata = response.get("metadata", {})

            # 如果LLM返回了扁平结构或包含 extracted_data（旧格式），尝试提取
            if not report_data and response:
                # 可能是直接返回了报告内容
                report_data = response
            elif "extracted_data" in response and not report_data:
                # LLM 返回了旧格式，尝试从 extracted_data 中提取
                extracted = response.get("extracted_data", {})
                if extracted and isinstance(extracted, dict):
                    report_data = extracted

            # 计算字数
            total_words = 0
            for key, value in report_data.items():
                if isinstance(value, str):
                    total_words += len(value)

            result = {
                "analysis_report": report_data,
                "metadata": {
                    "depth": depth,
                    "depth_label": self.DEPTH_CONFIG[depth]["name"],
                    "generated_at": datetime.utcnow().isoformat(),
                    "word_count": total_words,
                },
            }

            self.logger.info(
                f"Report generated successfully, depth={depth}, words={total_words}",
                extra={"depth": depth, "word_count": total_words, "event": "report_generate_complete"},
            )

            return result

        except Exception as e:
            self.logger.error(
                f"Report generation failed: {e}",
                extra={"depth": depth, "error": str(e), "event": "report_generate_error"},
            )
            raise

    def report_to_markdown(self, report_data: Dict[str, Any], theme: str) -> str:
        """将报告数据转换为Markdown格式"""
        report = report_data.get("analysis_report", {})
        metadata = report_data.get("metadata", {})

        md_parts = []

        # 标题
        md_parts.append(f"# {theme} — 经验分析报告")
        md_parts.append("")
        md_parts.append(f"> **报告深度**：{metadata.get('depth_label', '标准版')}  ")
        md_parts.append(f"> **生成时间**：{metadata.get('generated_at', '')[:10]}  ")
        md_parts.append(f"> **字数**：约 {metadata.get('word_count', 0)} 字")
        md_parts.append("")
        md_parts.append("---")
        md_parts.append("")

        # 章节映射：key -> (标题, 是否必须)
        sections = [
            ("executive_summary", "执行摘要", True),
            ("case_background", "案例背景", True),
            ("four_layer_structure", "头-身-足-包四层结构", False),
            ("methodology_framework", "方法论框架", True),
            ("key_steps_analysis", "关键步骤详解", True),
            ("decision_logic_analysis", "决策逻辑深度分析", False),
            ("process_obstacle_mapping", "流程-障碍映射", False),
            ("root_cause_analysis", "5Why根因链分析", False),
            ("obstacles_and_risks", "风险与挑战分析", True),
            ("tools_and_scripts", "工具与话术清单", True),
            ("application_guidance", "应用建议", True),
            ("critical_success_factors", "关键成功因素", False),
            ("value_assessment", "价值评估", True),
            ("lessons_learned", "可迁移的经验教训", True),
            ("references", "相关概念与理论引用", False),
            ("three_review_assessment", "三审定稿评估", False),
        ]

        for key, title, required in sections:
            content = report.get(key)
            if content:
                # 确保内容是字符串（LLM可能返回dict/list）
                if isinstance(content, dict):
                    import json
                    content = json.dumps(content, ensure_ascii=False, indent=2)
                elif isinstance(content, list):
                    content = "\n".join(f"- {item}" for item in content)
                elif not isinstance(content, str):
                    content = str(content)

                md_parts.append(f"## {title}")
                md_parts.append("")
                md_parts.append(content)
                md_parts.append("")
                md_parts.append("---")
                md_parts.append("")

        return "\n".join(md_parts)


# 全局实例
report_service = ReportService()
