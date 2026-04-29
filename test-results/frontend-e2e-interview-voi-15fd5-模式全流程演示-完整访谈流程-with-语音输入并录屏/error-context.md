# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: frontend\e2e\interview-voice-simulation.spec.ts >> 保险产品说明会访谈 —— 语音模式全流程演示 >> 完整访谈流程 with 语音输入并录屏
- Location: frontend\e2e\interview-voice-simulation.spec.ts:86:3

# Error details

```
Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
Call log:
  - navigating to "/", waiting until "load"

```

# Test source

```ts
  1   | import { test, expect, Page } from '@playwright/test';
  2   | 
  3   | /**
  4   |  * 经验萃取AI系统 —— 保险产品说明会访谈全流程演示（语音模式）
  5   |  *
  6   |  * 目标：录制完整的端到端演示视频（MP4）
  7   |  * 主题：如何举办成功的保险产品说明会（产说会）
  8   |  * 流程：创建访谈 → 生成蓝图 → 语音模式12轮对话 → 完成访谈 → 查看成果 → 生成标准报告
  9   |  *
  10  |  * 技术方案：
  11  |  * - 后端 BaiduRealtimeASRClient 启用 MOCK_TRANSCRIPTION 模式
  12  |  * - Playwright 启动 Chrome 时注入 --use-fake-device-for-media-stream
  13  |  * - 前端录音、WebSocket、转写流程完全真实，无需修改
  14  |  */
  15  | 
  16  | // ============ 辅助函数 ============
  17  | 
  18  | /** 获取当前阶段文本 */
  19  | async function getCurrentState(page: Page): Promise<string> {
  20  |   const stateText = await page.locator('text=/当前阶段：/').textContent();
  21  |   return stateText?.replace('当前阶段：', '').trim() || '';
  22  | }
  23  | 
  24  | /** 等待 AI 回复完成（"整理中..."消失） */
  25  | async function waitForAiResponse(page: Page, timeoutMs: number = 120_000) {
  26  |   // 先等待 AI 加载指示器出现（表示请求已发出）
  27  |   await page.waitForSelector('text=AI正在深入分析您的回答', { timeout: 5000 }).catch(() => {
  28  |     // 可能已经很快完成，忽略
  29  |   });
  30  | 
  31  |   // 等待"整理中..."从"下一轮"按钮上消失
  32  |   await page.waitForFunction(
  33  |     () => {
  34  |       const buttons = document.querySelectorAll('button');
  35  |       for (const btn of buttons) {
  36  |         if (btn.textContent?.includes('整理中...')) {
  37  |           return false;
  38  |         }
  39  |       }
  40  |       return true;
  41  |     },
  42  |     { timeout: timeoutMs }
  43  |   );
  44  |   // 额外等待一下，确保 DOM 更新完成
  45  |   await page.waitForTimeout(1500);
  46  | }
  47  | 
  48  | /** 等待语音转写结果完全出现（FIN_TEXT） */
  49  | async function waitForTranscription(page: Page, timeoutMs: number = 180_000) {
  50  |   // 等待当前轮次的转录文本出现（通过 "当前轮次（待提交）" 标签定位，避免误匹配历史消息）
  51  |   await page.waitForFunction(
  52  |     () => {
  53  |       const labels = Array.from(document.querySelectorAll('span'));
  54  |       const roundLabel = labels.find(s => s.textContent?.includes('当前轮次（待提交）'));
  55  |       if (!roundLabel) return false;
  56  |       const container = roundLabel.closest('div.flex-col');
  57  |       if (!container) return false;
  58  |       const textEl = container.querySelector('p.whitespace-pre-wrap');
  59  |       return textEl && textEl.textContent && textEl.textContent.length > 10;
  60  |     },
  61  |     { timeout: timeoutMs }
  62  |   );
  63  |   // 等待 FIN_TEXT 最终确认（预览消失，确认文本完整）
  64  |   await page.waitForFunction(
  65  |     () => {
  66  |       const labels = Array.from(document.querySelectorAll('span'));
  67  |       const roundLabel = labels.find(s => s.textContent?.includes('当前轮次（待提交）'));
  68  |       if (!roundLabel) return false;
  69  |       const container = roundLabel.closest('div.flex-col');
  70  |       if (!container) return false;
  71  |       const previewEl = container.querySelector('p.opacity-60');
  72  |       return !previewEl || previewEl.textContent === '';
  73  |     },
  74  |     { timeout: 5000 }
  75  |   );
  76  | }
  77  | 
  78  | /** 等待语音识别连接成功 */
  79  | async function waitForTranscriptionConnected(page: Page, timeoutMs: number = 15_000) {
  80  |   await page.waitForSelector('text=实时语音识别已连接', { timeout: timeoutMs });
  81  | }
  82  | 
  83  | // ============ 测试主体 ============
  84  | 
  85  | test.describe('保险产品说明会访谈 —— 语音模式全流程演示', () => {
  86  |   test('完整访谈流程 with 语音输入并录屏', async ({ page }) => {
  87  |     console.log('\n========== 演示开始 ==========');
  88  |     console.log('主题：如何举办成功的保险产品说明会（产说会）');
  89  |     console.log('预计轮次：6 轮（覆盖 6 个访谈阶段）');
  90  |     console.log('视频将保存至 test-results/ 目录\n');
  91  | 
  92  |     // ==================== Phase 1: 创建访谈 ====================
  93  | 
  94  |     // Step 1: 访问首页
  95  |     console.log('[Step 1] 访问首页');
> 96  |     await page.goto('/');
      |                ^ Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
  97  |     console.log('[完成] 已访问首页');
  98  | 
  99  |     await expect(page.locator('h1.text-5xl')).toContainText('经验萃取AI');
  100 |     await page.screenshot({ path: 'e2e/screenshots/voice_01_homepage.png' });
  101 | 
  102 |     // Step 2: 点击创建新访谈
  103 |     console.log('[Step 2] 点击"开始新的萃取访谈"');
  104 |     await page.getByText('开始新的萃取访谈').click();
  105 |     await expect(page.getByText('创建新访谈')).toBeVisible();
  106 |     await page.screenshot({ path: 'e2e/screenshots/voice_02_create_page.png' });
  107 | 
  108 |     // Step 3: 填写表单
  109 |     console.log('[Step 3] 填写访谈表单');
  110 |     await page.getByPlaceholder('例如：新任销售代表的异议处理技巧')
  111 |       .fill('如何举办成功的保险产品说明会（产说会）');
  112 |     await page.getByPlaceholder('描述该经验所在的业务场景和背景...')
  113 |       .fill('拥有10年保险行业经验，擅长组织大型保险产品说明会，年均举办50场以上，单场最高成交率达35%');
  114 |     await page.getByPlaceholder('例如：资深销售经理')
  115 |       .fill('资深保险营销总监');
  116 | 
  117 |     // 确保时长为 10 分钟
  118 |     const durationInput = page.locator('input[type="number"]');
  119 |     await durationInput.fill('10');
  120 | 
  121 |     await page.screenshot({ path: 'e2e/screenshots/voice_03_form_filled.png' });
  122 | 
  123 |     // Step 4: 提交表单，等待蓝图
  124 |     console.log('[Step 4] 提交表单，等待蓝图生成...');
  125 |     await page.click('button[type="submit"]');
  126 | 
  127 |     await page.waitForURL(/\/interviews\/.*\/blueprint/, { timeout: 60_000 });
  128 |     await expect(page.locator('text=访谈蓝图')).toBeVisible({ timeout: 120_000 });
  129 | 
  130 |     // 等待蓝图生成完成
  131 |     const generatingLocator = page.locator('text=AI正在生成访谈蓝图');
  132 |     if (await generatingLocator.isVisible().catch(() => false)) {
  133 |       console.log('[等待] 蓝图生成中...');
  134 |       await generatingLocator.waitFor({ state: 'hidden', timeout: 120_000 });
  135 |     }
  136 | 
  137 |     await page.screenshot({ path: 'e2e/screenshots/voice_04_blueprint.png' });
  138 |     console.log('[完成] 蓝图生成完毕');
  139 | 
  140 |     // Step 5: 确认蓝图并开始访谈
  141 |     console.log('[Step 5] 确认蓝图，进入访谈');
  142 |     const confirmBtn = page.getByText('确认蓝图并开始访谈');
  143 |     await confirmBtn.click();
  144 | 
  145 |     // 处理录音设置弹窗（如弹出）
  146 |     const recordingModal = page.locator('text=录音设置');
  147 |     if (await recordingModal.isVisible().catch(() => false)) {
  148 |       console.log('[处理] 关闭录音设置弹窗');
  149 |       await page.getByRole('button', { name: '开始访谈', exact: true }).click();
  150 |     }
  151 | 
  152 |     // 等待跳转到聊天页面
  153 |     await page.waitForURL(/\/interviews\/.*\/chat/, { timeout: 30_000 });
  154 |     await expect(page.getByText('完成访谈')).toBeVisible({ timeout: 30_000 });
  155 |     console.log('[完成] 已进入聊天页面');
  156 | 
  157 |     // Step 6: 等待开场问题出现
  158 |     console.log('[Step 6] 等待开场问题...');
  159 |     await page.waitForSelector('text=AI正在准备开场问题...', { timeout: 5000 }).catch(() => {});
  160 |     await page.waitForFunction(
  161 |       () => {
  162 |         const loadingText = document.querySelector('p.text-gray-600.font-medium');
  163 |         return !loadingText || loadingText.textContent !== 'AI正在准备开场问题...';
  164 |       },
  165 |       { timeout: 120_000 }
  166 |     );
  167 |     await page.waitForTimeout(3000);
  168 | 
  169 |     const initialState = await getCurrentState(page);
  170 |     console.log(`[初始状态] 当前阶段：${initialState}`);
  171 |     await page.screenshot({ path: 'e2e/screenshots/voice_05_chat_opening.png' });
  172 | 
  173 |     // ==================== Phase 2: 语音模式对话（12轮）====================
  174 | 
  175 |     // Step 7: 开启录音模式
  176 |     console.log('[Step 7] 开启录音模式');
  177 |     // 查找录音按钮（匹配"录音"或"录音中"）
  178 |     const recordingBtn = page.locator('button').filter({ hasText: /录音/ }).first();
  179 |     const recordingBtnText = await recordingBtn.textContent().catch(() => '');
  180 |     if (recordingBtnText.includes('录音') && !recordingBtnText.includes('录音中')) {
  181 |       await recordingBtn.click();
  182 |       console.log('[动作] 点击录音按钮开启录音');
  183 |     }
  184 | 
  185 |     // 等待录音中状态出现
  186 |     await expect(page.locator('text=录音中')).toBeVisible({ timeout: 10_000 });
  187 |     console.log('[完成] 录音模式已开启');
  188 | 
  189 |     // 等待实时语音识别连接
  190 |     console.log('[等待] 等待实时语音识别连接...');
  191 |     await waitForTranscriptionConnected(page, 15_000);
  192 |     console.log('[完成] 实时语音识别已连接');
  193 |     await page.screenshot({ path: 'e2e/screenshots/voice_06_recording_started.png' });
  194 | 
  195 |     // 6 轮对话循环（每阶段 1 轮）
  196 |     const maxRounds = 6;
```