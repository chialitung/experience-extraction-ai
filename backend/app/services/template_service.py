from typing import Dict, Any, List
from datetime import datetime


class TemplateService:
    """成果模板渲染服务

    根据访谈的结构化内容，按不同模板格式渲染最终成果。
    """

    TEMPLATE_METADATA = {
        "script_card": {
            "name": "话术卡",
            "description": "标准话术与应对策略，适合一线人员快速上手",
            "icon": "message-circle",
        },
        "checklist": {
            "name": "检查表",
            "description": "操作步骤检查清单，确保关键动作不遗漏",
            "icon": "check-square",
        },
        "flowchart": {
            "name": "流程图",
            "description": "决策流程与关键步骤，可视化操作路径",
            "icon": "git-branch",
        },
        "learning_card": {
            "name": "学习卡",
            "description": "知识点速记卡片，便于培训和复习",
            "icon": "book-open",
        },
        "case_study": {
            "name": "案例",
            "description": "完整案例分析，包含背景、过程、结果和启示",
            "icon": "file-text",
        },
    }

    @classmethod
    def list_templates(cls) -> List[Dict[str, str]]:
        """获取所有可用模板列表"""
        return [
            {"id": k, **v}
            for k, v in cls.TEMPLATE_METADATA.items()
        ]

    @classmethod
    def render(cls, template_id: str, data: Dict[str, Any]) -> str:
        """根据模板ID和数据渲染成果"""
        renderer = getattr(cls, f"_render_{template_id}", cls._render_default)
        return renderer(data)

    @classmethod
    def _render_script_card(cls, data: Dict[str, Any]) -> str:
        """渲染话术卡模板"""
        theme = data.get("theme", "未命名主题")
        steps = data.get("steps", [])
        principles = data.get("principles", [])
        tools = data.get("tools", [])
        risks = data.get("risks", [])

        lines = [
            f"# 📋 话术卡：{theme}",
            "",
            "> 💡 **使用说明**：以下话术为经验萃取精华，请根据实际场景灵活调整。",
            "",
            "---",
            "",
        ]

        if steps:
            lines.append("## 🎯 标准操作步骤")
            lines.append("")
            for i, step in enumerate(steps, 1):
                title = step.get("title") or step.get("name", f"步骤{i}")
                desc = step.get("description") or step.get("detail", "")
                lines.append(f"### 步骤{i}：{title}")
                if desc:
                    lines.append(f"{desc}")
                lines.append("")

        if tools:
            lines.append("## 🛠️ 推荐话术/工具")
            lines.append("")
            for tool in tools:
                name = tool.get("name") or tool.get("title", "")
                desc = tool.get("description") or tool.get("detail", "")
                usage = tool.get("usage_method") or tool.get("usage", "")
                lines.append(f"- **{name}**：{desc}")
                if usage:
                    lines.append(f"  - 使用方法：{usage}")
            lines.append("")

        if principles:
            lines.append("## 💡 核心原则")
            lines.append("")
            for p in principles:
                title = p.get("title") or p.get("name", "")
                desc = p.get("description") or p.get("detail", "")
                lines.append(f"- **{title}**：{desc}")
            lines.append("")

        if risks:
            lines.append("## ⚠️ 常见风险与应对")
            lines.append("")
            for r in risks:
                desc = r.get("description") or r.get("detail", "")
                prevention = r.get("prevention") or r.get("solution", "")
                lines.append(f"- **风险**：{desc}")
                if prevention:
                    lines.append(f"  - **应对**：{prevention}")
            lines.append("")

        lines.append("---")
        lines.append(f"\n*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        return "\n".join(lines)

    @classmethod
    def _render_checklist(cls, data: Dict[str, Any]) -> str:
        """渲染检查表模板"""
        theme = data.get("theme", "未命名主题")
        steps = data.get("steps", [])
        risks = data.get("risks", [])

        lines = [
            f"# ✅ 检查表：{theme}",
            "",
            "> 请在执行每项操作后勾选确认，确保关键动作不遗漏。",
            "",
            "---",
            "",
            "## 📋 操作检查项",
            "",
        ]

        for i, step in enumerate(steps, 1):
            title = step.get("title") or step.get("name", f"步骤{i}")
            desc = step.get("description") or step.get("detail", "")
            lines.append(f"- [ ] **{title}**")
            if desc:
                lines.append(f"  - {desc}")
        lines.append("")

        if risks:
            lines.append("## ⚠️ 风险检查项")
            lines.append("")
            for r in risks:
                desc = r.get("description") or r.get("detail", "")
                prevention = r.get("prevention") or r.get("solution", "")
                lines.append(f"- [ ] **风险排查**：{desc}")
                if prevention:
                    lines.append(f"  - 确认已采取：{prevention}")
            lines.append("")

        lines.append("---")
        lines.append(f"\n*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        return "\n".join(lines)

    @classmethod
    def _render_flowchart(cls, data: Dict[str, Any]) -> str:
        """渲染流程图模板（使用Mermaid语法）"""
        theme = data.get("theme", "未命名主题")
        steps = data.get("steps", [])
        decisions = data.get("decisions", [])

        lines = [
            f"# 🔄 流程图：{theme}",
            "",
            "> 以下为操作流程的可视化表示，支持在支持Mermaid的编辑器中渲染。",
            "",
            "---",
            "",
            "```mermaid",
            "flowchart TD",
        ]

        if steps:
            for i, step in enumerate(steps):
                title = step.get("title") or step.get("name", f"步骤{i+1}")
                node_id = f"S{i}"
                lines.append(f"    {node_id}[{title}]")
                if i > 0:
                    lines.append(f"    S{i-1} --> {node_id}")

        if decisions:
            for j, decision in enumerate(decisions):
                desc = decision.get("description") or decision.get("detail", "")
                node_id = f"D{j}"
                lines.append(f"    {node_id}{{{desc}}}")

        lines.append("```")
        lines.append("")

        if steps:
            lines.append("## 📖 步骤说明")
            lines.append("")
            for i, step in enumerate(steps, 1):
                title = step.get("title") or step.get("name", f"步骤{i}")
                desc = step.get("description") or step.get("detail", "")
                lines.append(f"{i}. **{title}**：{desc}")
            lines.append("")

        lines.append("---")
        lines.append(f"\n*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        return "\n".join(lines)

    @classmethod
    def _render_learning_card(cls, data: Dict[str, Any]) -> str:
        """渲染学习卡模板"""
        theme = data.get("theme", "未命名主题")
        principles = data.get("principles", [])
        tools = data.get("tools", [])
        risks = data.get("risks", [])

        lines = [
            f"# 📚 学习卡：{theme}",
            "",
            "---",
            "",
        ]

        if principles:
            lines.append("## 🧠 核心知识点")
            lines.append("")
            for i, p in enumerate(principles, 1):
                title = p.get("title") or p.get("name", "")
                desc = p.get("description") or p.get("detail", "")
                scenario = p.get("application_scenario") or p.get("scenario", "")
                lines.append(f"### 知识点{i}：{title}")
                lines.append(f"{desc}")
                if scenario:
                    lines.append(f"\n**应用场景**：{scenario}")
                lines.append("")

        if tools:
            lines.append("## 🛠️ 必备工具")
            lines.append("")
            for tool in tools:
                name = tool.get("name") or tool.get("title", "")
                desc = tool.get("description") or tool.get("detail", "")
                usage = tool.get("usage_method") or tool.get("usage", "")
                lines.append(f"- **{name}**：{desc}")
                if usage:
                    lines.append(f"  - 用法：{usage}")
            lines.append("")

        if risks:
            lines.append("## ⚠️ 易错点提醒")
            lines.append("")
            for r in risks:
                desc = r.get("description") or r.get("detail", "")
                prevention = r.get("prevention") or r.get("solution", "")
                lines.append(f"- ❌ **错误**：{desc}")
                if prevention:
                    lines.append(f"  - ✅ **正确做法**：{prevention}")
            lines.append("")

        lines.append("---")
        lines.append(f"\n*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        return "\n".join(lines)

    @classmethod
    def _render_case_study(cls, data: Dict[str, Any]) -> str:
        """渲染案例模板"""
        theme = data.get("theme", "未命名主题")
        background = data.get("background", "")
        steps = data.get("steps", [])
        principles = data.get("principles", [])
        tools = data.get("tools", [])
        risks = data.get("risks", [])
        decisions = data.get("decisions", [])

        lines = [
            f"# 📖 案例：{theme}",
            "",
            "---",
            "",
        ]

        lines.append("## 🎯 案例背景")
        lines.append("")
        lines.append(background or "（背景信息待补充）")
        lines.append("")

        if steps:
            lines.append("## 📝 处理过程")
            lines.append("")
            for i, step in enumerate(steps, 1):
                title = step.get("title") or step.get("name", f"步骤{i}")
                desc = step.get("description") or step.get("detail", "")
                lines.append(f"### 步骤{i}：{title}")
                lines.append(f"{desc}")
                lines.append("")

        if decisions:
            lines.append("## 🤔 关键决策")
            lines.append("")
            for d in decisions:
                desc = d.get("description") or d.get("detail", "")
                lines.append(f"- {desc}")
            lines.append("")

        if principles:
            lines.append("## 💡 经验启示")
            lines.append("")
            for p in principles:
                title = p.get("title") or p.get("name", "")
                desc = p.get("description") or p.get("detail", "")
                lines.append(f"- **{title}**：{desc}")
            lines.append("")

        if tools:
            lines.append("## 🛠️ 使用工具")
            lines.append("")
            for tool in tools:
                name = tool.get("name") or tool.get("title", "")
                desc = tool.get("description") or tool.get("detail", "")
                lines.append(f"- **{name}**：{desc}")
            lines.append("")

        if risks:
            lines.append("## ⚠️ 风险总结")
            lines.append("")
            for r in risks:
                desc = r.get("description") or r.get("detail", "")
                prevention = r.get("prevention") or r.get("solution", "")
                lines.append(f"- **{desc}**")
                if prevention:
                    lines.append(f"  - 预防措施：{prevention}")
            lines.append("")

        lines.append("---")
        lines.append(f"\n*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        return "\n".join(lines)

    @classmethod
    def _render_default(cls, data: Dict[str, Any]) -> str:
        """默认渲染：综合文本"""
        theme = data.get("theme", "未命名主题")
        steps = data.get("steps", [])
        lines = [f"# 成果：{theme}", ""]
        for i, step in enumerate(steps, 1):
            title = step.get("title") or step.get("name", f"步骤{i}")
            desc = step.get("description") or step.get("detail", "")
            lines.append(f"## {title}")
            lines.append(desc)
            lines.append("")
        return "\n".join(lines)
