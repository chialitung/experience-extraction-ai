import os
import json
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader, Template
from app.core.config import settings


class PromptManager:
    """提示词管理器：加载、渲染和管理提示词模板"""
    
    def __init__(self, prompts_dir: Optional[str] = None):
        if prompts_dir is None:
            # 默认提示词目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            prompts_dir = os.path.join(current_dir, "..", "prompts")
        
        self.prompts_dir = os.path.abspath(prompts_dir)
        self.env = Environment(
            loader=FileSystemLoader(self.prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._cache: Dict[str, Template] = {}
    
    def load_template(self, template_path: str) -> Template:
        """加载提示词模板"""
        if template_path not in self._cache:
            template = self.env.get_template(template_path)
            self._cache[template_path] = template
        return self._cache[template_path]
    
    def render(self, template_path: str, variables: Dict[str, Any]) -> str:
        """渲染提示词模板"""
        template = self.load_template(template_path)
        return template.render(**variables)
    
    def get_system_prompt(self, interview_config: Dict[str, Any]) -> str:
        """获取系统级提示词
        
        注入：角色定义 + 专家画像适配 + 蓝图指导 + 实时分析结果
        """
        base_prompt = self.render("system/role_definition.md", {})
        
        # ===== 专家画像适配 =====
        expert_profile = interview_config.get("expert_profile")
        if expert_profile and expert_profile.get("profile_type"):
            base_prompt += f"\n\n## 【专家沟通适配】（当前已识别）\n"
            base_prompt += f"- 沟通风格：{expert_profile.get('type_label_cn', '未识别')}\n"
            base_prompt += f"- 推断置信度：{expert_profile.get('confidence', 0)}\n"
            base_prompt += f"- 适配策略：{expert_profile.get('adaptation_strategy', '标准策略')}\n"
            base_prompt += f"- 即时行动建议：{expert_profile.get('suggestion', '维持标准提问方式')}\n"
        else:
            base_prompt += f"\n\n## 【专家沟通适配】（样本不足，尚未识别）\n"
            base_prompt += "当前专家画像暂未建立（回答样本不足3轮）。请使用标准提问策略，同时注意观察专家回答特征。\n"
        
        # ===== 蓝图关联注入 =====
        blueprint = interview_config.get("blueprint")
        if blueprint and isinstance(blueprint, dict):
            base_prompt += f"\n\n## 【访谈蓝图指导】\n"
            base_prompt += f"访谈主题：{blueprint.get('theme', interview_config.get('theme', ''))}\n"
            core_goal = blueprint.get("core_goal", "")
            if core_goal:
                base_prompt += f"核心目标：{core_goal}\n"
            
            # 注入当前步骤的关键挖掘点
            current_step = interview_config.get("current_step", "")
            six_steps = blueprint.get("six_steps", [])
            if six_steps and current_step:
                for step in six_steps:
                    step_name = step.get("step", "")
                    # 匹配中英文状态名
                    if step_name and (step_name == current_step or step_name in str(current_step)):
                        key_focus = step.get("key_focus", "")
                        suggested_questions = step.get("suggested_questions", [])
                        if key_focus:
                            base_prompt += f"当前步骤重点挖掘：{key_focus}\n"
                        if suggested_questions:
                            base_prompt += f"蓝图建议的追问方向：{'; '.join(suggested_questions[:3])}\n"
                        break
            
            # 注入五维价值评估
            value = blueprint.get("value_assessment", {})
            if value:
                base_prompt += f"\n价值评估（五维：高价值、有难度、常使用、急需要、覆盖广）：\n"
                dim_names = {"gold": "高价值", "wood": "有难度", "water": "常使用", "fire": "急需要", "earth": "覆盖广"}
                for k, v in value.items():
                    if k in dim_names:
                        base_prompt += f"  - {dim_names[k]}：{v}\n"
                    elif k != "reasons":
                        base_prompt += f"  - {k}：{v}\n"
        
        # ===== 实时内容分析结果注入 =====
        analysis = interview_config.get("content_analysis")
        if analysis and isinstance(analysis, dict):
            base_prompt += f"\n\n## 【实时内容分析结果】（程序化分析，供你参考）\n"

            # 颗粒度
            depth = analysis.get("depth", "")
            depth_score = analysis.get("depth_score", 0)
            depth_reason = analysis.get("depth_reason", "")
            if depth:
                base_prompt += f"- 回答颗粒度：{depth}（评分{depth_score}）\n"
                base_prompt += f"  分析：{depth_reason}\n"

            # 偏离检测
            off_topic = analysis.get("off_topic", False)
            off_conf = analysis.get("off_topic_confidence", 0)
            off_reason = analysis.get("off_topic_reason", "")
            if off_topic or off_conf > settings.TOPIC_DRIFT_PROMPT_INJECT:
                base_prompt += f"- 偏离检测：{'⚠️ 疑似偏离' if off_topic else '未偏离'}（置信度{off_conf}）\n"
                base_prompt += f"  分析：{off_reason}\n"
                if off_topic:
                    base_prompt += "  【行动】请生成确认性问题，礼貌地将专家拉回当前步骤主题。\n"
                    suggested_correction = analysis.get("suggested_correction")
                    if suggested_correction:
                        base_prompt += f"  【建议引导话术】{suggested_correction}\n"

            # 信息缺口
            gaps = analysis.get("gaps", [])
            if gaps:
                base_prompt += f"- 当前信息缺口：\n"
                for gap in gaps[:6]:
                    base_prompt += f"  · {gap}\n"
                base_prompt += "  【行动】请优先针对以上缺口生成追问问题。\n"
            else:
                base_prompt += "- 当前信息缺口：暂无显著缺口，可考虑推进到下一步。\n"

        # ===== 时间预算注入 =====
        time_budget = interview_config.get("time_budget")
        if time_budget and isinstance(time_budget, dict):
            base_prompt += f"\n\n## 【时间预算控制】\n"
            base_prompt += f"- 访谈总时长：{time_budget.get('total_duration_min', 30)} 分钟\n"
            base_prompt += f"- 说话速度参考：{time_budget.get('words_per_minute_range', '150-250')} 字/分钟\n"
            base_prompt += f"- 当前阶段字数预算：约 {time_budget.get('stage_word_budget', 1000)} 字\n"
            base_prompt += f"- 本阶段已进行：{time_budget.get('current_turns', 0)} 轮\n"
            base_prompt += f"- 本阶段建议最多：{time_budget.get('max_turns_per_stage', 3)} 轮\n"
            remaining = time_budget.get('remaining_turns', 0)
            base_prompt += f"- 剩余可追问轮数：{remaining} 轮\n"

            # 新增字数预算信息
            stage_word_count = time_budget.get('current_stage_word_count', 0)
            stage_word_limit = time_budget.get('stage_word_limit', 0)
            remaining_words = time_budget.get('remaining_words', 0)
            base_prompt += f"- 当前阶段已用字数：{stage_word_count} 字\n"
            base_prompt += f"- 当前阶段字数上限：{stage_word_limit} 字\n"
            base_prompt += f"- 当前阶段剩余字数：{remaining_words} 字\n"

            if remaining <= 0:
                base_prompt += "【紧急】本阶段轮数已用完，请在下一个问题中总结已收集的信息，然后明确告知专家进入下一阶段。\n"
            elif remaining == 1:
                base_prompt += "【提醒】本阶段仅剩1轮，请在下一个问题中收集最后的关键信息，然后准备推进到下一阶段。\n"

            if remaining_words <= 0:
                base_prompt += "【紧急】本阶段字数预算已用完，请在下一个问题中总结已收集的信息，然后明确告知专家进入下一阶段。\n"
            elif remaining_words <= stage_word_limit * 0.2 and stage_word_limit > 0:
                base_prompt += "【提醒】本阶段字数预算即将用完（剩余20%以下），请精简问题，准备推进到下一阶段。\n"

            base_prompt += "你必须严格控制每个阶段的轮数和字数，不要在一个阶段停留过久。当信息基本收集完毕后，主动推进到下一阶段。\n"

        return base_prompt
    
    def get_blueprint_prompt(self, theme: str, background: str,
                            expert_role: str, duration: int,
                            output_format: Any) -> str:
        """获取蓝图生成提示词"""
        if isinstance(output_format, list):
            format_desc = ", ".join(output_format)
        else:
            format_desc = str(output_format)
        return self.render("tasks/blueprint_generation.md", {
            "theme": theme,
            "background": background or "未提供",
            "expert_role": expert_role or "未指定",
            "duration": duration,
            "output_format": format_desc,
        })
    
    def get_question_prompt(self, theme: str, current_step: str,
                           extracted_framework: Dict, information_gaps: list,
                           expert_profile: Dict, value_assessment: Dict,
                           recent_qa: list) -> str:
        """获取问题生成提示词"""
        return self.render("tasks/question_generation.md", {
            "theme": theme,
            "current_step": current_step,
            "extracted_framework": json.dumps(extracted_framework, ensure_ascii=False, indent=2),
            "information_gaps": json.dumps(information_gaps, ensure_ascii=False, indent=2),
            "expert_profile": json.dumps(expert_profile, ensure_ascii=False, indent=2),
            "value_assessment": json.dumps(value_assessment, ensure_ascii=False, indent=2),
            "recent_qa": json.dumps(recent_qa, ensure_ascii=False, indent=2),
        })
    
    def get_extraction_prompt(self, expert_answer: str, 
                             existing_structure: Dict,
                             current_step: str) -> str:
        """获取内容萃取提示词"""
        return self.render("tasks/content_extraction.md", {
            "expert_answer": expert_answer,
            "existing_structure": json.dumps(existing_structure, ensure_ascii=False, indent=2),
            "current_step": current_step,
        })
    
    def get_packaging_prompt(self, structured_content: Dict,
                            output_formats: List[str], theme: str) -> str:
        """获取成果封装提示词（支持多形式/全套生成）"""
        return self.render("tasks/output_packaging.md", {
            "structured_content": json.dumps(structured_content, ensure_ascii=False, indent=2),
            "output_formats": output_formats,
            "theme": theme,
        })

    def get_opening_prompt(self, theme: str, background: str,
                          expert_role: str, duration: int,
                          output_formats: List[str],
                          expert_profile: Optional[Dict] = None,
                          blueprint: Optional[Dict] = None) -> str:
        """获取访谈开场白生成提示词（四维破冰开场）"""
        # 构建产出形式描述
        format_name_map = {
            "script_card": "话术卡",
            "checklist": "操作检查表",
            "flowchart": "流程图要点",
            "learning_card": "学习卡片",
            "case_study": "案例复盘",
        }
        format_labels = [format_name_map.get(f, f) for f in output_formats]
        output_desc = "、".join(format_labels) if format_labels else "话术卡、检查表等实用工具"

        # 构建专家画像提示
        profile_hint = ""
        if expert_profile and expert_profile.get("profile_type"):
            pt = expert_profile.get("profile_type", "")
            strategy = expert_profile.get("adaptation_strategy", "")
            profile_hint = f"已识别专家类型：{pt}。适配策略：{strategy}"
        else:
            profile_hint = "专家画像尚未建立（样本不足），请使用通用开场策略。"

        # 注入蓝图核心目标
        core_goal = ""
        if blueprint and isinstance(blueprint, dict):
            core_goal = blueprint.get("core_goal", "")

        return self.render("tasks/opening_generation.md", {
            "theme": theme,
            "background": background or "未提供具体背景",
            "expert_role": expert_role or "",
            "duration": duration,
            "output_formats_desc": output_desc,
            "expert_profile_hint": profile_hint,
            "core_goal": core_goal or "将隐性经验转化为可复制的显性知识",
        })


# 全局提示词管理器实例
prompt_manager = PromptManager()
