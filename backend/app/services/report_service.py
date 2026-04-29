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

### 价值评估（金木水火土）
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
    "value_assessment": "价值评估（金木水火土五维分析）",
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
4. 价值评估章节必须包含金木水火土五维的具体评分和解释
5. 应用建议要具体，包含适用场景、前提条件、常见变体和注意事项
6. 所有内容必须基于访谈实际数据，不得编造
7. 字数严格控制在 {config['word_target']} 范围内
8. 输出必须是合法JSON，所有字符串值必须使用双引号
"""
        return prompt

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

        # 根据深度级别设置 max_tokens：brief 3000, standard 6000, deep 10000
        max_tokens_map = {"brief": 3000, "standard": 6000, "deep": 10000}
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
            ("methodology_framework", "方法论框架", True),
            ("key_steps_analysis", "关键步骤详解", True),
            ("decision_logic_analysis", "决策逻辑深度分析", False),
            ("obstacles_and_risks", "风险与挑战分析", True),
            ("tools_and_scripts", "工具与话术清单", True),
            ("application_guidance", "应用建议", True),
            ("value_assessment", "价值评估", True),
            ("lessons_learned", "可迁移的经验教训", True),
            ("references", "相关概念与理论引用", False),
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
