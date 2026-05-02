# 访谈完成流程设计

**日期**:2026-05-02
**问题**:访谈状态机推进到 `completed` 时,计时器仍在跑、无后续提示、无跳转,用户以为系统卡死。

## 目标

当 `current_state` 推进到 `completed` 时:
1. 本地暂停计时器(冻结显示);
2. 隐藏输入框,展示两个按钮:【完成访谈】、【继续访谈】;
3. 点【完成访谈】→ 阻塞式 Modal 提示"正在生成成果材料"→ 调后端打包 → 跳转成果页;
4. 点【继续访谈】→ 后端将状态回退到 `confirmation` + `active` → 输入框重启用 → 计时继续。

## 触发条件

仅在状态机自然推进至 `current_state === 'completed'` 时显示完成/继续按钮。手动操作不在本次范围。

## 前端设计

### `frontend/src/pages/InterviewChatPage.tsx`

- 新增 effect:监听 `currentInterview.current_state`,若为 `completed`:
  - 把本地 `timing.status` 设为 `paused`(不调后端 timer API);
  - 隐藏 message input 区,渲染两个按钮:
    - **【完成访谈】** 主色实心
    - **【继续访谈】** 次色描边
- 新增本地 state `isFinalizing`(布尔)和 `finalizeError`(string|null)。
- 点【完成访谈】:
  1. 设 `isFinalizing = true` → 渲染全屏阻塞 Modal:
     ```
     标题:正在生成访谈成果材料
     正文:系统正在分析访谈对话并生成话术卡 / 检查表 / 流程图等成果。
           通常需要 20–60 秒,请勿关闭页面或刷新浏览器。
     底部:转圈动画
     ```
  2. 调 `completeInterview(id)`(已存在):
     - 成功 → `navigate('/interviews/:id/output')`;
     - 失败 → Modal 切换为错误态,显示 `finalizeError`,提供 "重试" 和 "返回访谈" 按钮。
- 点【继续访谈】:
  1. 调新加的 `resumeInterview(id)`;
  2. 成功 → `setCurrentInterview(updated)`(后端返回新的 interview 对象,`current_state === 'confirmation'`,`status === 'active'`)→ 输入框因 disable 条件不再满足而重启用 → `setTiming({status: 'running'})` 让本地计时恢复;
  3. 失败 → toast 错误,状态保持 `completed`。

### `frontend/src/hooks/useInterview.ts`

新增 `resumeInterview(id)`,沿用 `completeInterview` 的错误处理风格:

```ts
const resumeInterview = useCallback(async (id: string) => {
  store.setIsLoading(true);
  try {
    const response = await interviewApi.resume(id);
    store.setCurrentInterview(response.data);
    return response.data;
  } catch (error: any) {
    store.setError(error.response?.data?.detail || '继续访谈失败');
    throw error;
  } finally {
    store.setIsLoading(false);
  }
}, []);
```

返回的 `response.data` 是更新后的 Interview 对象。

### `frontend/src/services/api.ts`

```ts
resume: (id: string) =>
  api.post<Interview>(`/interviews/${id}/resume`),
```

## 后端设计

### 新接口:`POST /interviews/{interview_id}/resume`

`backend/app/api/v1/interviews.py`,跟 `complete_interview` 同一区域:

```python
@router.post("/{interview_id}/resume", response_model=InterviewResponse)
async def resume_interview(
    interview_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: Optional[User] = Depends(get_current_active_user_optional),
):
    """从 completed 状态回退到 confirmation 阶段,允许专家继续补充。"""
    user_id = resolve_user_filter(current_user)
    interview = await service.get_interview(interview_id, user_id=user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    if interview.current_state != InterviewState.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail="Interview is not in completed state; nothing to resume.",
        )
    updated = await service.resume_interview(interview_id)
    return updated
```

### `backend/app/services/interview_service.py` 新方法

```python
async def resume_interview(self, interview_id: str) -> Interview:
    """把已 completed 的访谈回退到 confirmation 状态以允许继续补充。"""
    interview = await self._get_interview_for_update(interview_id)
    if interview.current_state != InterviewState.COMPLETED:
        raise ValueError("Interview is not completed")

    interview.current_state = InterviewState.CONFIRMATION
    interview.status = InterviewStatus.ACTIVE
    history = list(interview.state_history or [])
    history.append({
        "action": "resumed",
        "from": "completed",
        "to": "confirmation",
        "timestamp": datetime.utcnow().isoformat(),
    })
    interview.state_history = history

    await self.db.commit()
    await self.db.refresh(interview)
    return interview
```

### `send_message` 守卫

`backend/app/api/v1/interviews.py:send_message` 在调 `generate_ai_response` 之前增加:

```python
if interview.current_state == InterviewState.COMPLETED:
    raise HTTPException(
        status_code=409,
        detail="Interview already completed; call /resume to continue or /complete to finalize.",
    )
```

`send_message_stream` 同样加这个守卫。

## 文件清单

修改:

- `backend/app/api/v1/interviews.py` — 加 `/resume` 端点 + `send_message`/`send_message_stream` completed 守卫
- `backend/app/services/interview_service.py` — 加 `resume_interview(id)` 方法
- `frontend/src/services/api.ts` — 加 `resume(id)`
- `frontend/src/hooks/useInterview.ts` — 加 `resumeInterview` hook
- `frontend/src/pages/InterviewChatPage.tsx` — completed 检测 effect、本地暂停计时、双按钮、阻塞 Modal、错误处理

不动:

- 数据库 schema(state 枚举不变,只是行为变了)
- 后端 timer API(本地暂停不调后端)

## 错误处理

| 场景 | 行为 |
|------|------|
| `/complete` 失败(LLM 报错、网络) | Modal 切换错误态,显示 detail,提供"重试"(再调一次)与"返回访谈"(关 Modal,保留 completed 状态) |
| `/resume` 失败 | toast 显示错误,UI 保持 completed,用户可重试或选择完成 |
| `send_message` 在 completed 时被强行调用(绕过 UI) | 后端 409 拒绝,前端按一般错误展示 |

## 测试要点

- 后端单测:
  - `resume_interview` 成功路径(状态回退 + state_history 追加)
  - `resume_interview` 在非 completed 状态下抛 ValueError
  - `send_message` / `send_message_stream` 在 completed 状态返回 409
- 前端手动验证(列出 golden path):
  1. 自然完成访谈 → 看到双按钮、计时器冻结
  2. 点【完成访谈】→ Modal 出现 → 跳成果页
  3. 点【继续访谈】→ 输入框激活、计时恢复、可继续提问
  4. 完成访谈失败 → Modal 错误态 + 重试可用
