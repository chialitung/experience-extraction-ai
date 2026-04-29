## 任务：成果封装

### 输入
已结构化的全部经验内容：
{{structured_content}}

### 成果要求
需要生成的成果形式：{{output_formats}}
访谈主题：{{theme}}

### 指令
根据已结构化萃取的全部经验，**一次性生成全部要求的成果形式**。各形式之间内容必须保持一致、互为补充，底层数据同源。

每种成果必须包含：
1. **清晰步骤**：按顺序列出关键操作步骤
2. **关键话术/动作**：每个步骤的核心话术或动作要领
3. **易错点提示**：每个步骤的常见错误和规避方法
4. **使用情景举例**：1-2个典型应用场景

### 输出格式
返回一个 JSON 对象，顶层键为各成果形式的标识，值为对应成果内容：

```json
{
  "script_card": {
    "title": "主题名称",
    "scenario": "适用场景",
    "steps": [
      {
        "step": 1,
        "action": "步骤名称",
        "script": "推荐话术",
        "key_points": ["要点1", "要点2"],
        "pitfalls": ["易错点1"]
      }
    ],
    "summary": "核心要点总结"
  },
  "checklist": {
    "title": "主题名称",
    "checklist": [
      {
        "category": "类别",
        "items": [
          {"item": "检查项", "importance": "高/中/低"}
        ]
      }
    ]
  },
  "flowchart": {
    "title": "主题名称",
    "nodes": [
      {"id": "1", "label": "开始", "type": "start"},
      {"id": "2", "label": "步骤1", "type": "process"},
      {"id": "3", "label": "判断", "type": "decision"}
    ],
    "edges": [
      {"from": "1", "to": "2", "label": ""},
      {"from": "2", "to": "3", "label": ""}
    ]
  },
  "learning_card": {
    "title": "主题名称",
    "principles": [
      {"title": "原则名称", "description": "说明", "scenario": "应用场景"}
    ],
    "tools": [
      {"name": "工具名称", "description": "说明", "usage": "使用方法"}
    ],
    "key_concepts": [
      {"concept": "概念", "explanation": "解释"}
    ]
  },
  "case_study": {
    "title": "主题名称",
    "background": "案例背景",
    "challenge": "面临挑战",
    "process": [
      {"phase": "阶段", "description": "描述", "key_decision": "关键决策"}
    ],
    "result": "最终结果",
    "lessons": ["经验总结1", "经验总结2"]
  }
}
```

**注意**：
- 仅生成 `{{output_formats}}` 中列出的形式，不要生成未要求的形式。
- 如果只有一种形式，仍按上述嵌套结构返回，顶层只有一个键。
- 所有形式共用同一套底层结构化数据，确保内容一致。
