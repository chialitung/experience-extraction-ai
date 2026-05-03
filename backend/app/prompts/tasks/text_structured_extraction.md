# 任务：从访谈记录中批量提取结构化经验内容

你是一位资深的企业知识管理顾问和经验萃取专家。你的任务是从已清理的访谈对话记录中，系统性地提取和结构化经验知识。

## 输入

以下是一段经过清理的经验萃取访谈对话记录。记录已去除寒暄、口头禅、跑题等无效内容，只保留了有价值的问答。

访谈主题：{{theme}}
业务背景：{{background or "未提供"}}
专家角色：{{expert_role or "未指定"}}

访谈对话记录：
```
{% for msg in messages %}
[{{ "访谈者" if msg.role == "interviewer" else "专家" }}] {{ msg.content }}
{% endfor %}
```

## 提取要求

请从上述访谈记录中提取以下结构化内容：

### 1. 关键步骤 (steps)

提取专家描述的核心操作流程和关键动作：
- 每个步骤包含：order（序号）、title（标题）、description（描述）、details（详细说明，可选）
- 按执行顺序排列
- 不超过7个核心步骤

### 2. 核心原则/方法论 (principles)

提取专家遵循的核心原则、方法论框架：
- 每个原则包含：title（标题）、description（描述）、application_scenario（应用场景，可选）

### 3. 工具与话术 (tools)

提取专家使用的具体工具、模板、话术、检查表等：
- 每个工具包含：name（名称）、description（描述）、usage_method（使用方法，可选）

### 4. 风险与障碍 (risks)

提取专家提到的常见错误、困难点、易忽略点：
- 每个风险包含：type（类型：error/difficulty/overlook）、description（描述）、prevention（预防措施，可选）

### 5. 关键决策点 (decisions)

提取专家在过程中做出的关键决策：
- 每个决策包含：description（决策描述）、context（决策背景，可选）

### 6. 场景变量 (scenario_variables) — 专家版高阶数据

提取专家提到的不同场景及适配策略：
- 每个场景包含：scenario（场景名称）、variables（关键变量列表）、adaptation（适配策略）

### 7. 关键成功因素 (success_factors) — 专家版高阶数据

提取3-5个最关键的成功因素：
- 每个因素包含：factor（因素名称）、gold（高价值）/wood（有难度）/water（常使用）/fire（急需要）/earth（覆盖广）五维评分（1-10）、priority（优先级1为最高）

### 8. 根因链 (root_cause_chains) — 专家版高阶数据

对每个主要风险，追溯根因链：
- 每个风险包含：risk_id（风险标识）、risk_description（风险描述）、chain（5层根因链列表：表面现象→直接原因→间接原因→深层原因→根因）、prevention（预防措施）

## 输出格式

你必须严格按照以下JSON结构输出：

```json
{
  "steps": [
    {"order": 1, "title": "...", "description": "...", "details": "..."}
  ],
  "principles": [
    {"title": "...", "description": "...", "application_scenario": "..."}
  ],
  "tools": [
    {"name": "...", "description": "...", "usage_method": "..."}
  ],
  "risks": [
    {"type": "error|difficulty|overlook", "description": "...", "prevention": "..."}
  ],
  "decisions": [
    {"description": "...", "context": "..."}
  ],
  "scenario_variables": [
    {"scenario": "...", "variables": ["..."], "adaptation": "..."}
  ],
  "success_factors": [
    {"factor": "...", "gold": 8, "wood": 7, "water": 9, "fire": 6, "earth": 7, "priority": 1}
  ],
  "root_cause_chains": [
    {"risk_id": "risk_1", "risk_description": "...", "chain": ["表面现象", "直接原因", "间接原因", "深层原因", "根因"], "prevention": "..."}
  ]
}
```

## 重要约束

1. 只输出JSON，不要输出任何解释性文字
2. 确保JSON格式合法，字符串使用双引号
3. 所有提取内容必须基于访谈实际记录，不得编造
4. 如果某类内容在记录中未出现，返回空数组 []
5. 保持专家原意，不要过度概括或抽象化
6. 对于模糊的表述，优先保留原样而不是猜测
