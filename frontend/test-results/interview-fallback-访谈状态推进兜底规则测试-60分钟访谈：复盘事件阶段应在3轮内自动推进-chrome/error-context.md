# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: interview-fallback.spec.ts >> 访谈状态推进兜底规则测试 >> 60分钟访谈：复盘事件阶段应在3轮内自动推进
- Location: e2e\interview-fallback.spec.ts:80:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('text=经验萃取AI')
Expected: visible
Error: strict mode violation: locator('text=经验萃取AI') resolved to 3 elements:
    1) <h1 class="text-xl font-bold text-gray-900">经验萃取AI</h1> aka getByRole('complementary').getByRole('heading', { name: '经验萃取AI' })
    2) <h1 class="text-lg font-bold text-gray-900">经验萃取AI</h1> aka getByText('经验萃取AI').nth(1)
    3) <h1 class="text-5xl font-bold text-gray-900 mb-6">经验萃取AI</h1> aka getByRole('main').getByRole('heading', { name: '经验萃取AI' })

Call log:
  - Expect "toBeVisible" with timeout 120000ms
  - waiting for locator('text=经验萃取AI')

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - complementary [ref=e4]:
    - generic [ref=e5]:
      - heading "经验萃取AI" [level=1] [ref=e6]
      - paragraph [ref=e7]: 智能化访谈辅助系统
    - navigation [ref=e8]:
      - link "首页" [ref=e9] [cursor=pointer]:
        - /url: /
        - img [ref=e10]
        - text: 首页
      - link "访谈列表" [ref=e13] [cursor=pointer]:
        - /url: /interviews
        - img [ref=e14]
        - text: 访谈列表
      - link "新建访谈" [ref=e16] [cursor=pointer]:
        - /url: /interviews/new
        - img [ref=e17]
        - text: 新建访谈
    - generic [ref=e18]:
      - link "设置" [ref=e19] [cursor=pointer]:
        - /url: /settings
        - img [ref=e20]
        - text: 设置
      - link "登录" [ref=e23] [cursor=pointer]:
        - /url: /login
        - img [ref=e24]
        - text: 登录
  - main [ref=e27]:
    - generic [ref=e29]:
      - generic [ref=e30]:
        - heading "经验萃取AI" [level=1] [ref=e31]
        - paragraph [ref=e32]: 将业务专家的隐性经验转化为可复制的显性知识。 通过AI驱动的结构化访谈，系统化地完成经验萃取。
        - link "开始新的萃取访谈" [ref=e33] [cursor=pointer]:
          - /url: /interviews/new
          - img [ref=e34]
          - text: 开始新的萃取访谈
          - img [ref=e36]
      - generic [ref=e38]:
        - generic [ref=e39]:
          - img [ref=e41]
          - heading "智能访谈引导" [level=3] [ref=e43]
          - paragraph [ref=e44]: AI根据六步流程自动提问，深度挖掘专家经验，确保不遗漏关键细节。
        - generic [ref=e45]:
          - img [ref=e47]
          - heading "实时结构化萃取" [level=3] [ref=e49]
          - paragraph [ref=e50]: 访谈过程中自动提取步骤、工具、风险点，实时构建知识框架。
        - generic [ref=e51]:
          - img [ref=e53]
          - heading "成果自动封装" [level=3] [ref=e55]
          - paragraph [ref=e56]: 访谈结束后自动生成话术卡、检查表、流程图等可直接使用的工具。
      - generic [ref=e57]:
        - heading "萃取流程" [level=2] [ref=e58]
        - generic [ref=e59]:
          - generic [ref=e60]:
            - generic [ref=e61]:
              - generic [ref=e62]: "1"
              - heading "配置访谈" [level=3] [ref=e63]
              - paragraph [ref=e64]: 设定主题与目标
            - img [ref=e65]
          - generic [ref=e67]:
            - generic [ref=e68]:
              - generic [ref=e69]: "2"
              - heading "生成蓝图" [level=3] [ref=e70]
              - paragraph [ref=e71]: AI规划访谈路径
            - img [ref=e72]
          - generic [ref=e74]:
            - generic [ref=e75]:
              - generic [ref=e76]: "3"
              - heading "深度访谈" [level=3] [ref=e77]
              - paragraph [ref=e78]: 多轮对话萃取
            - img [ref=e79]
          - generic [ref=e82]:
            - generic [ref=e83]: "4"
            - heading "成果输出" [level=3] [ref=e84]
            - paragraph [ref=e85]: 自动生成工具
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
  52  |   await page.waitForFunction(
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
> 87  |     await expect(page.locator('text=经验萃取AI')).toBeVisible();
      |                                               ^ Error: expect(locator).toBeVisible() failed
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
  153 | 
  154 |     // 断言：初始状态应为"复盘事件"
  155 |     expect(initialState).toContain('复盘事件');
  156 | 
  157 |     // Step 7-9: 逐轮回答，观察状态变化
  158 |     let currentState = initialState;
  159 |     let turnCount = 0;
  160 |     const maxTurns = 3;
  161 | 
  162 |     for (let i = 0; i < maxTurns; i++) {
  163 |       turnCount = i + 1;
  164 |       console.log(`\n========== 第 ${turnCount} 轮回答 ==========`);
  165 | 
  166 |       // 发送回答
  167 |       await sendMessageAndWait(page, EXPERT_ANSWERS[i]);
  168 |       await page.screenshot({ path: `e2e/screenshots/06-turn-${turnCount}.png` });
  169 | 
  170 |       // 检查状态
  171 |       const newState = await getCurrentState(page);
  172 |       console.log(`[第${turnCount}轮后] 当前阶段：${newState}`);
  173 | 
  174 |       // 如果状态已推进，记录并继续（LLM 可能在少于3轮时就建议推进，这是正常的）
  175 |       if (newState !== currentState && !newState.includes('复盘事件')) {
  176 |         console.log(`[推进] 状态已从"${currentState}"推进到"${newState}"（第${turnCount}轮后）`);
  177 |         currentState = newState;
  178 | 
  179 |         // 如果已经推进到建构框架或更后面，测试成功
  180 |         if (newState.includes('建构框架') || newState.includes('挖掘细节') ||
  181 |             newState.includes('识别障碍') || newState.includes('提炼工具') ||
  182 |             newState.includes('复述确认')) {
  183 |           console.log(`\n✅ 测试通过：状态在第${turnCount}轮后成功推进！`);
  184 |           break;
  185 |         }
  186 |       } else {
  187 |         currentState = newState;
```