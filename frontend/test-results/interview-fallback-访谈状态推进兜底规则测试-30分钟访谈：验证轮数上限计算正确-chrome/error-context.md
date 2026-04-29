# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: interview-fallback.spec.ts >> 访谈状态推进兜底规则测试 >> 30分钟访谈：验证轮数上限计算正确
- Location: e2e\interview-fallback.spec.ts:215:3

# Error details

```
Error: page.waitForFunction: Target page, context or browser has been closed
```

# Test source

```ts
  1   | import { test, expect, Page } from '@playwright/test';
  2   | 
  3   | /**
  4   |  * 经验萃取AI系统 —— 兜底规则仿真测试
  5   |  *
  6   |  * 测试目标：验证访谈状态推进的五层兜底机制是否正常工作
  7   |  * 测试方式：通过 Playwright 打开真实浏览器，模拟完整的访谈流程
  8   |  *
  9   |  * 背景：此前 60 分钟访谈在复盘事件阶段 stuck 14 轮未能推进
  10  |  * 修复后预期：3 轮内应自动从"复盘事件"推进到"建构框架"（轮数兜底 MAX_TURNS_PER_STATE = 3）
  11  |  */
  12  | 
  13  | // 测试数据：模拟专家回答（基于之前 stuck 的真实对话记录）
  14  | const EXPERT_ANSWERS = [
  15  |   // 第1轮：案例背景 + 冲突 + 行动 + 结果概述
  16  |   `大概在去年的时候，我遇到一个做产业园区的客户，业务比较复杂，涉及政府审批和资金流。
  17  | 第一次见面时，我问他们最近有没有在资金流上的困惑或困难，他说有。
  18  | 我就跟他分析了资金流不畅对项目进度、施工安排和资金周转的影响，还引用了类似项目延误几个月的案例。
  19  | 客户虽然一开始回应比较模糊，但后续问了具体案例和解决方案，表现出兴趣。
  20  | 我于是主动建议了项目调研，最终客户同意试点合作，建立了信任关系。`,
  21  | 
  22  |   // 第2轮：补充具体动作细节
  23  |   `当时我是这样切入的：
  24  | 我先问"你们最近有没有在资金流上有一些困惑或是困难？"他说有。
  25  | 我就跟他分析说，如果资金流不畅，可能会拖延整个项目进度，影响到施工安排和资金周转。
  26  | 我还提到，如果资金问题不能及时解决，可能会导致工期延误和资金回笼不及时。
  27  | 数据方面我引用了一个类似项目的例子，说资金无法及时到位往往延误几个月。
  28  | 客户后来问了有没有类似案例和解决方案，我就提议安排项目调研深入分析资金流的具体问题。`,
  29  | 
  30  |   // 第3轮：补充调研结果和后续反馈
  31  |   `调研后我整理了详细报告，包含资金流不畅的具体表现、影响项目的关键环节，以及几种可行的优化方案，例如改善资金周转流程、提高资金调度效率等。
  32  | 报告中还结合了行业成功案例的对比数据，展示我们的方案如何在实际操作中帮助客户提高效率。
  33  | 客户对优化方案表示认可，同意在下一步进行试点实施。
  34  | 虽然这是初步合作，不是大规模推广，但客户已经开始愿意与我们合作了。`,
  35  | ];
  36  | 
  37  | // 辅助函数：获取当前阶段文本
  38  | async function getCurrentState(page: Page): Promise<string> {
  39  |   const stateText = await page.locator('text=/当前阶段：/').textContent();
  40  |   return stateText?.replace('当前阶段：', '').trim() || '';
  41  | }
  42  | 
  43  | // 辅助函数：等待 AI 回复完成
  44  | async function waitForAiResponse(page: Page, timeoutMs: number = 120_000) {
  45  |   // 先等待 AI 加载指示器出现（表示请求已发出）
  46  |   await page.waitForSelector('text=AI正在深入分析您的回答', { timeout: 5000 }).catch(() => {
  47  |     // 可能已经很快完成，忽略
  48  |   });
  49  | 
  50  |   // 等待发送按钮变为可用（isLoading / isStreaming 结束）
  51  |   // 使用更精确的选择器：包含 Send 图标的按钮
> 52  |   await page.waitForFunction(
      |              ^ Error: page.waitForFunction: Target page, context or browser has been closed
  53  |     () => {
  54  |       const btns = document.querySelectorAll('button');
  55  |       for (const btn of btns) {
  56  |         const svg = btn.querySelector('svg');
  57  |         if (svg && btn.classList.contains('bg-primary-600')) {
  58  |           return !(btn as HTMLButtonElement).disabled;
  59  |         }
  60  |       }
  61  |       return false;
  62  |     },
  63  |     { timeout: timeoutMs }
  64  |   );
  65  |   // 额外等待一下，确保 DOM 更新完成
  66  |   await page.waitForTimeout(1500);
  67  | }
  68  | 
  69  | // 辅助函数：发送消息并等待回复
  70  | async function sendMessageAndWait(page: Page, content: string) {
  71  |   const textarea = page.getByPlaceholder('请输入您的回答...');
  72  |   await textarea.fill(content);
  73  |   await page.keyboard.press('Enter');
  74  |   console.log(`[测试] 已发送回答，等待 AI 回复...`);
  75  |   await waitForAiResponse(page);
  76  |   console.log(`[测试] AI 回复完成`);
  77  | }
  78  | 
  79  | test.describe('访谈状态推进兜底规则测试', () => {
  80  |   test('60分钟访谈：复盘事件阶段应在3轮内自动推进', async ({ page }) => {
  81  |     console.log('\n========== 测试开始 ==========');
  82  |     console.log('目标：验证轮数兜底（MAX_TURNS_PER_STATE=3）是否正常触发');
  83  | 
  84  |     // Step 1: 访问首页
  85  |     console.log('\n[Step 1] 访问首页');
  86  |     await page.goto('/');
  87  |     await expect(page.locator('text=经验萃取AI')).toBeVisible();
  88  |     await page.screenshot({ path: 'e2e/screenshots/01-homepage.png' });
  89  | 
  90  |     // Step 2: 点击创建新访谈
  91  |     console.log('[Step 2] 点击"开始新的萃取访谈"');
  92  |     await page.getByText('开始新的萃取访谈').click();
  93  |     await expect(page.getByText('创建新访谈')).toBeVisible();
  94  |     await page.screenshot({ path: 'e2e/screenshots/02-create-page.png' });
  95  | 
  96  |     // Step 3: 填写表单
  97  |     console.log('[Step 3] 填写访谈表单');
  98  |     await page.getByPlaceholder('例如：新任销售代表的异议处理技巧').fill('金融大客户关系经营');
  99  |     await page.getByPlaceholder('描述该经验所在的业务场景和背景...').fill('拥有15年大客户销售经验，年均签约额过亿，擅长产业园区客户开发');
  100 |     await page.getByPlaceholder('例如：资深销售经理').fill('资深销售总监');
  101 | 
  102 |     // 确保时长为 60 分钟
  103 |     const durationInput = page.locator('input[type="number"]');
  104 |     await durationInput.fill('60');
  105 | 
  106 |     await page.screenshot({ path: 'e2e/screenshots/03-form-filled.png' });
  107 | 
  108 |     // Step 4: 提交表单
  109 |     console.log('[Step 4] 提交表单，等待蓝图生成');
  110 |     await page.click('button[type="submit"]');
  111 | 
  112 |     // 等待跳转到蓝图页面
  113 |     await page.waitForURL(/\/interviews\/.*\/blueprint/);
  114 |     await expect(page.locator('text=访谈蓝图')).toBeVisible({ timeout: 60_000 });
  115 | 
  116 |     // 等待蓝图生成完成（如果有加载动画）
  117 |     const generatingLocator = page.locator('text=AI正在生成访谈蓝图');
  118 |     if (await generatingLocator.isVisible().catch(() => false)) {
  119 |       console.log('[等待] 蓝图生成中...');
  120 |       await generatingLocator.waitFor({ state: 'hidden', timeout: 120_000 });
  121 |     }
  122 | 
  123 |     await page.screenshot({ path: 'e2e/screenshots/04-blueprint.png' });
  124 |     console.log('[完成] 蓝图生成完毕');
  125 | 
  126 |     // Step 5: 确认蓝图并开始访谈
  127 |     console.log('[Step 5] 确认蓝图，进入访谈');
  128 |     const confirmBtn = page.getByText('确认蓝图并开始访谈');
  129 |     await confirmBtn.click();
  130 | 
  131 |     // 等待跳转到聊天页面
  132 |     await page.waitForURL(/\/interviews\/.*\/chat/);
  133 |     await expect(page.locator('text=访谈中')).toBeVisible({ timeout: 30_000 });
  134 |     console.log('[完成] 已进入聊天页面');
  135 | 
  136 |     // Step 6: 等待开场问题出现
  137 |     console.log('[Step 6] 等待开场问题...');
  138 |     // 等待 AI 消息气泡出现（assistant role 的 rounded-lg 消息）或开场问题加载完成
  139 |     await page.waitForSelector('text=AI正在准备开场问题...', { timeout: 5000 }).catch(() => {});
  140 |     // 等待加载状态消失，出现 AI 消息
  141 |     await page.waitForFunction(
  142 |       () => {
  143 |         const loadingText = document.querySelector('p.text-gray-600.font-medium');
  144 |         return !loadingText || loadingText.textContent !== 'AI正在准备开场问题...';
  145 |       },
  146 |       { timeout: 120_000 }
  147 |     );
  148 |     await page.waitForTimeout(3000); // 等待开场问题渲染完成
  149 | 
  150 |     const initialState = await getCurrentState(page);
  151 |     console.log(`[初始状态] 当前阶段：${initialState}`);
  152 |     await page.screenshot({ path: 'e2e/screenshots/05-chat-opening.png' });
```