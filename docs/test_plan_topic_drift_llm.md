# 测试计划：LLM 语义版主题偏离检测

> 版本: v1.0  
> 分支: `feature/topic-drift-llm`  
> 日期: 2026-04-29

---

## 1. 测试目标

验证主题偏离检测从规则引擎升级为「规则 + LLM 灰区仲裁」后的正确性、稳定性和性能。

| 测试维度 | 目标 |
|---|---|
| 功能正确性 | 阈值调整、灰区触发、LLM 语义判定、三处入口集成均按设计工作 |
| 边界安全 | 空输入、超长输入、LLM 异常、mock 模式等边界条件下不崩溃 |
| 性能影响 | LLM 灰区调用不会显著增加单次问答延迟 |
| 向后兼容 | 规则引擎置信度 ≥0.35 或 ≤0.15 时不触发 LLM，行为与旧版一致 |

---

## 2. 测试范围

| 组件 | 测试类型 | 覆盖内容 |
|---|---|---|
| `content_analyzer.py` | 单元测试 | `detect_off_topic()` 阈值变化（0.45→0.35） |
| `interview_service.py` | 单元测试 | `_detect_topic_drift_llm()` 方法本体 |
| `interview_service.py` | 单元测试 | `_get_last_ai_question()` 辅助方法 |
| `interview_service.py` | 集成测试 | 三处入口灰区仲裁触发逻辑 |
| 前后端联调 | E2E 测试 | 实际访谈流程中主题偏离场景的检测效果 |

---

## 3. 测试环境

| 层级 | 环境配置 |
|---|---|
| 单元/集成 | pytest + AsyncMock + MagicMock，无需真实数据库 |
| API 集成 | FastAPI TestClient + aiosqlite 内存数据库 |
| E2E | 本地完整环境：后端 `localhost:8000` + 前端 `localhost:5173` |
| LLM | 优先使用 **mock 模式**（无需真实 API Key）；真实 LLM 验证时指定 Moonshot/DeepSeek |

---

## 4. 单元测试用例

### 4.1 ContentAnalyzer — 阈值调整验证

**文件**: `backend/tests/test_content_analyzer_topic_drift.py`

| 用例ID | 场景 | 输入 | 预期结果 | 备注 |
|---|---|---|---|---|
| CA-001 | 置信度 0.35 恰好等于新阈值 | 回答含 1 个偏离短语 + 主题匹配度低 | `is_off_topic=True`, `confidence=0.35` | 验证阈值边界 |
| CA-002 | 置信度 0.34 低于阈值（不偏离） | 回答含 1 个偏离短语 | `is_off_topic=False`, `confidence=0.34` | 旧版 0.45 会判偏离，新版不判 |
| CA-003 | 置信度 0.50 明显高于阈值 | 多个偏离信号叠加 | `is_off_topic=True`, `confidence≥0.50` | 规则直接判定，不走 LLM |
| CA-004 | 置信度 0.10 明显低于阈值 | 正常回答，关键词匹配度高 | `is_off_topic=False`, `confidence≤0.10` | 规则直接判定，不走 LLM |
| CA-005 | 空回答 | `answer=""` | `is_off_topic=False`, `confidence=0.0` | 防御性边界 |
| CA-006 | 超长回答无结构 | 500字以上，无列表/步骤 | `confidence` 增加 0.15 | 验证"发散"检测规则 |

### 4.2 InterviewService — `_get_last_ai_question()`

**文件**: `backend/tests/test_interview_service_topic_drift.py`

| 用例ID | 场景 | Mock 数据 | 预期结果 |
|---|---|---|---|
| IQ-001 | 正常获取最近 AI 问题 | messages = [user, assistant, user, assistant] | 返回最后一条 assistant.content |
| IQ-002 | 无 AI 消息（全是用户） | messages = [user, user] | 返回 `""` |
| IQ-003 | AI 消息 content 为空 | messages = [assistant(content="")] | 返回 `""` |
| IQ-004 | 消息列表为空 | messages = [] | 返回 `""` |

### 4.3 InterviewService — `_detect_topic_drift_llm()`

| 用例ID | 场景 | Mock 策略 | 预期结果 |
|---|---|---|---|
| LLM-001 | 正常判定为偏离 | `llm_service.generate_json` 返回 `{"is_off_topic":true,"confidence":0.85,"reason":"xxx"}` | 返回 `is_off_topic=True`, `confidence=0.85`, reason 含 `[LLM语义判定]` |
| LLM-002 | 正常判定为不偏离 | `llm_service.generate_json` 返回 `{"is_off_topic":false,"confidence":0.15,"reason":"xxx"}` | 返回 `is_off_topic=False`, `confidence=0.15` |
| LLM-003 | LLM 返回缺失字段 | `generate_json` 返回 `{}` | 保守回退：`is_off_topic=False`, `confidence=0.5`, reason 含默认值 |
| LLM-004 | LLM 调用抛出异常 | `generate_json` 抛 `RuntimeError` | 保守回退：`is_off_topic=False`, `confidence=0.1`, 记录 error 日志 |
| LLM-005 | confidence 越界（>1.0） | `generate_json` 返回 `confidence=1.5` | 裁剪为 `1.0` |
| LLM-006 | confidence 越界（<0.0） | `generate_json` 返回 `confidence=-0.5` | 裁剪为 `0.0` |
| LLM-007 | mock 模式下运行 | `llm_service.mock_mode=True` | 依赖 `_get_mock_json_response` 行为，但系统提示含"topic drift"，可能落入 else 分支返回 `{"message":"模拟响应"}` —— 需验证不会崩溃 |

---

## 5. 集成测试用例

### 5.1 三处入口灰区触发验证

**文件**: `backend/tests/test_interview_service_topic_drift_integration.py`

**策略**: 对 `generate_ai_response`、`_generate_ai_question_only`、`generate_ai_response_stream` 分别测试，mock `content_analyzer.full_analysis` 返回不同置信度，验证是否触发 LLM。

| 用例ID | 入口方法 | 规则置信度 | 是否应触发 LLM | 验证点 |
|---|---|---|---|---|
| INT-001 | `generate_ai_response` | 0.40（灰区） | ✅ 是 | `_detect_topic_drift_llm` 被调用 1 次，analysis_dict 被覆盖 |
| INT-002 | `generate_ai_response` | 0.50（≥0.35） | ❌ 否 | `_detect_topic_drift_llm` 未被调用，保留规则结果 |
| INT-003 | `generate_ai_response` | 0.10（≤0.15） | ❌ 否 | `_detect_topic_drift_llm` 未被调用，保留规则结果 |
| INT-004 | `_generate_ai_question_only` | 0.25（灰区） | ✅ 是 | 同上 |
| INT-005 | `_generate_ai_question_only` | 0.00 | ❌ 否 | 同上 |
| INT-006 | `generate_ai_response_stream` | 0.20（灰区） | ✅ 是 | 同上 |
| INT-007 | `generate_ai_response_stream` | 0.35（边界） | ❌ 否 | `0.35` 不满足 `< 0.35`，不触发 |
| INT-008 | `generate_ai_response_stream` | 0.15（边界） | ❌ 否 | `0.15` 不满足 `> 0.15`，不触发 |

**Mock 要点**:
- `service.get_interview` → 返回 mock interview（含 theme/blueprint/current_state）
- `service._get_structured_content` → 返回 `{}`
- `service._count_turns_in_current_state` → 返回 2
- `service._get_stage_word_count` → 返回 500
- `content_analyzer.full_analysis` → 返回 `AnswerAnalysis(off_topic_confidence=xxx, ...)`
- `llm_service.generate_json` → AsyncMock（灰区用例）

---

## 6. E2E / 手动测试用例

### 6.1 文本模式访谈（`generate_ai_response`）

| 用例ID | 场景 | 操作步骤 | 预期结果 | 验证方式 |
|---|---|---|---|---|
| E2E-001 | 专家正常回答（不偏离） | 创建访谈 → 文本回答切题内容 | AI 继续追问，无偏离提示 | 前端页面观察 + 后端日志确认 `off_topic=false` |
| E2E-002 | 专家明显跑题（高置信度） | 回答内容完全不相关（如谈天气、政治） | AI 生成引导话术拉回主题 | 观察 AI 回复是否含"回到主题"类措辞 |
| E2E-003 | 专家聊新案例但仍在主题内（灰区） | 回答"说到这个，我想到另一个客户..."然后展开 | 可能触发灰区 → LLM 判定为不偏离 → AI 继续追问 | 后端日志搜索 `topic_drift_llm_arbitration`，确认 confidence 在灰区 |
| E2E-004 | 专家回答极短 | 只回复"嗯""好的" | `confidence` 极低，不触发 LLM | 后端日志确认 `off_topic_confidence` |

### 6.2 语音模式访谈（`_generate_ai_question_only`）

| 用例ID | 场景 | 操作步骤 | 预期结果 |
|---|---|---|---|
| E2E-005 | 语音回答后点击"下一轮" | 录音回答后完成轮次 | 后端 `/round/complete` 正常 200，清洗后进入 AI 提问生成 |
| E2E-006 | 语音回答含偏离内容 | 录音中混入无关闲聊 | 清洗后内容若触发灰区，LLM 仲裁后生成拉回主题的问题 |

### 6.3 流式模式访谈（`generate_ai_response_stream`）

| 用例ID | 场景 | 操作步骤 | 预期结果 |
|---|---|---|---|
| E2E-007 | 流式实时对话中灰区触发 | 专家回答处于灰区 | LLM 调用在流开始前完成，不阻塞流式输出；AI 最终回复正确 |

---

## 7. 性能测试

| 用例ID | 场景 | 指标 | 预期 |
|---|---|---|---|
| PERF-001 | 灰区触发时的单次延迟 | 从用户发送消息到 AI 开始流式输出的耗时 | LLM 仲裁增加 ≤1500ms（单次 JSON 调用） |
| PERF-002 | 高频灰区触发 | 连续 10 轮都落入灰区 | 每轮均正确触发，无内存泄漏 |
| PERF-003 | mock 模式下延迟 | mock 模式不调用真实 API | 延迟增加 ≈0ms |

---

## 8. 回归测试

| 用例ID | 场景 | 验证点 |
|---|---|---|
| REG-001 | 状态推进兜底机制 | 确认 `_should_force_advance` 五层兜底不受主题偏离改动影响 |
| REG-002 | 专家画像更新 | 确认 expert_profile 分析仍在第 3 轮后触发 |
| REG-003 | 结构化内容提取 | 确认 `structured_update` 仍正常注入 system prompt |
| REG-004 | 完整访谈流程 | 30 分钟文本访谈走完全流程，无异常中断 |

---

## 9. 测试执行顺序

```
第1轮：单元测试（pytest backend/tests/）
  └─ 4.1 ContentAnalyzer 阈值
  └─ 4.2 _get_last_ai_question
  └─ 4.3 _detect_topic_drift_llm
  └─ 5.1 三处入口灰区触发

第2轮：API 集成测试（pytest backend/tests/test_interviews.py + 新增）
  └─ 创建访谈 → 发送消息 → 验证响应中 content_analysis.off_topic 字段

第3轮：本地 E2E（浏览器 + 后端日志）
  └─ 6.1 文本模式
  └─ 6.2 语音模式
  └─ 6.3 流式模式

第4轮：回归测试
  └─ 8.1 ~ 8.4
```

---

## 10. 测试通过标准

| 标准 | 要求 |
|---|---|
| 单元测试通过率 | 100% |
| 集成测试通过率 | 100% |
| linter 报错 | 0 |
| E2E 阻塞 BUG | 0 |
| E2E 非阻塞 BUG | ≤2（需记录并评估） |
| 性能退化 | 单次问答延迟增加 ≤1500ms |

---

## 11. 附录：关键日志事件

测试期间关注后端日志中的以下事件：

| 事件名 | 含义 | 出现场景 |
|---|---|---|
| `topic_drift_llm_arbitration` | LLM 灰区仲裁完成 | 灰区触发时 |
| `topic_drift_llm_error` | LLM 仲裁失败 | LLM 调用异常时 |
| `llm_json_success` | LLM JSON 调用成功 | 每次 LLM 调用 |
| `llm_json_error` | LLM JSON 调用失败 | 网络/Key 问题时 |
