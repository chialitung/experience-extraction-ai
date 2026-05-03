## 任务：生成下一轮问题

### 当前访谈状态
- 主题：{{theme}}
- 当前流程阶段：{{current_step}}
- 已萃取关键信息框架：{{extracted_framework}}
- 本次待澄清的信息缺口：{{information_gaps}}
- 专家画像标签：{{expert_profile}}
- 价值匹配度：{{value_assessment}}

### 历史对话记忆（最近3轮）
{{recent_qa}}

### 指令
1. 针对"信息缺口"，生成1个主要问题（选择最适合的问题类型）
2. 如信息缺口较大，额外生成1个辅助问题
3. 根据"专家画像"调整问题措辞
4. 确保问题能推进当前流程阶段的目标
5. 在问题后简要说明：此问题旨在获取什么信息，对应哪个价值维度

### 输出格式
```json
{
  "thinking": "分析当前状态和信息缺口，说明为什么选择这个问题类型",
  "primary_question": {
    "type": "探索性",
    "content": "具体的问题内容",
    "purpose": "获取第二步的具体动作细节",
    "value_dimension": "有难度",
    "adaptation_note": "针对不善言辞型专家，问题已拆解为更具体的子问题"
  },
  "follow_up": {
    "type": "假设性",
    "content": "辅助问题内容",
    "trigger_condition": "如果专家回答仍不够具体"
  },
  "structured_update": {
    "steps": [],
    "principles": [],
    "tools": [],
    "risks": []
  }
}
```
