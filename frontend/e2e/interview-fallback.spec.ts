import { test, expect, Page } from '@playwright/test';

/**
 * 经验萃取AI系统 —— 兜底规则仿真测试
 *
 * 测试目标：验证访谈状态推进的五层兜底机制是否正常工作
 * 测试方式：通过 Playwright 打开真实浏览器，模拟完整的访谈流程
 *
 * 背景：此前 60 分钟访谈在复盘事件阶段 stuck 14 轮未能推进
 * 修复后预期：3 轮内应自动从"复盘事件"推进到"建构框架"（轮数兜底 MAX_TURNS_PER_STATE = 3）
 */

// 测试数据：模拟专家回答（基于之前 stuck 的真实对话记录）
const EXPERT_ANSWERS = [
  // 第1轮：案例背景 + 冲突 + 行动 + 结果概述
  `大概在去年的时候，我遇到一个做产业园区的客户，业务比较复杂，涉及政府审批和资金流。
第一次见面时，我问他们最近有没有在资金流上的困惑或困难，他说有。
我就跟他分析了资金流不畅对项目进度、施工安排和资金周转的影响，还引用了类似项目延误几个月的案例。
客户虽然一开始回应比较模糊，但后续问了具体案例和解决方案，表现出兴趣。
我于是主动建议了项目调研，最终客户同意试点合作，建立了信任关系。`,

  // 第2轮：补充具体动作细节
  `当时我是这样切入的：
我先问"你们最近有没有在资金流上有一些困惑或是困难？"他说有。
我就跟他分析说，如果资金流不畅，可能会拖延整个项目进度，影响到施工安排和资金周转。
我还提到，如果资金问题不能及时解决，可能会导致工期延误和资金回笼不及时。
数据方面我引用了一个类似项目的例子，说资金无法及时到位往往延误几个月。
客户后来问了有没有类似案例和解决方案，我就提议安排项目调研深入分析资金流的具体问题。`,

  // 第3轮：补充调研结果和后续反馈
  `调研后我整理了详细报告，包含资金流不畅的具体表现、影响项目的关键环节，以及几种可行的优化方案，例如改善资金周转流程、提高资金调度效率等。
报告中还结合了行业成功案例的对比数据，展示我们的方案如何在实际操作中帮助客户提高效率。
客户对优化方案表示认可，同意在下一步进行试点实施。
虽然这是初步合作，不是大规模推广，但客户已经开始愿意与我们合作了。`,
];

// 辅助函数：获取当前阶段文本
async function getCurrentState(page: Page): Promise<string> {
  const stateText = await page.locator('text=/当前阶段：/').textContent();
  return stateText?.replace('当前阶段：', '').trim() || '';
}

// 辅助函数：等待 AI 回复完成
async function waitForAiResponse(page: Page, timeoutMs: number = 120_000) {
  // 先等待 AI 加载指示器出现（表示请求已发出）
  await page.waitForSelector('text=AI正在深入分析您的回答', { timeout: 5000 }).catch(() => {
    // 可能已经很快完成，忽略
  });

  // 等待发送按钮变为可用（isLoading / isStreaming 结束）
  // 使用更精确的选择器：包含 Send 图标的按钮
  await page.waitForFunction(
    () => {
      const btns = document.querySelectorAll('button');
      for (const btn of btns) {
        const svg = btn.querySelector('svg');
        if (svg && btn.classList.contains('bg-primary-600')) {
          return !(btn as HTMLButtonElement).disabled;
        }
      }
      return false;
    },
    { timeout: timeoutMs }
  );
  // 额外等待一下，确保 DOM 更新完成
  await page.waitForTimeout(1500);
}

// 辅助函数：发送消息并等待回复
async function sendMessageAndWait(page: Page, content: string) {
  const textarea = page.getByPlaceholder('请输入您的回答...');
  await textarea.fill(content);
  await page.keyboard.press('Enter');
  console.log(`[测试] 已发送回答，等待 AI 回复...`);
  await waitForAiResponse(page);
  console.log(`[测试] AI 回复完成`);
}

test.describe('访谈状态推进兜底规则测试', () => {
  test('60分钟访谈：复盘事件阶段应在3轮内自动推进', async ({ page }) => {
    console.log('\n========== 测试开始 ==========');
    console.log('目标：验证轮数兜底（MAX_TURNS_PER_STATE=3）是否正常触发');

    // Step 1: 访问首页
    console.log('\n[Step 1] 访问首页');
    await page.goto('/');
    await expect(page.locator('text=经验萃取AI')).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/01-homepage.png' });

    // Step 2: 点击创建新访谈
    console.log('[Step 2] 点击"开始新的萃取访谈"');
    await page.getByText('开始新的萃取访谈').click();
    await expect(page.getByText('创建新访谈')).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/02-create-page.png' });

    // Step 3: 填写表单
    console.log('[Step 3] 填写访谈表单');
    await page.getByPlaceholder('例如：新任销售代表的异议处理技巧').fill('金融大客户关系经营');
    await page.getByPlaceholder('描述该经验所在的业务场景和背景...').fill('拥有15年大客户销售经验，年均签约额过亿，擅长产业园区客户开发');
    await page.getByPlaceholder('例如：资深销售经理').fill('资深销售总监');

    // 确保时长为 60 分钟
    const durationInput = page.locator('input[type="number"]');
    await durationInput.fill('60');

    await page.screenshot({ path: 'e2e/screenshots/03-form-filled.png' });

    // Step 4: 提交表单
    console.log('[Step 4] 提交表单，等待蓝图生成');
    await page.click('button[type="submit"]');

    // 等待跳转到蓝图页面
    await page.waitForURL(/\/interviews\/.*\/blueprint/);
    await expect(page.locator('text=访谈蓝图')).toBeVisible({ timeout: 60_000 });

    // 等待蓝图生成完成（如果有加载动画）
    const generatingLocator = page.locator('text=AI正在生成访谈蓝图');
    if (await generatingLocator.isVisible().catch(() => false)) {
      console.log('[等待] 蓝图生成中...');
      await generatingLocator.waitFor({ state: 'hidden', timeout: 120_000 });
    }

    await page.screenshot({ path: 'e2e/screenshots/04-blueprint.png' });
    console.log('[完成] 蓝图生成完毕');

    // Step 5: 确认蓝图并开始访谈
    console.log('[Step 5] 确认蓝图，进入访谈');
    const confirmBtn = page.getByText('确认蓝图并开始访谈');
    await confirmBtn.click();

    // 等待跳转到聊天页面
    await page.waitForURL(/\/interviews\/.*\/chat/);
    await expect(page.locator('text=访谈中')).toBeVisible({ timeout: 30_000 });
    console.log('[完成] 已进入聊天页面');

    // Step 6: 等待开场问题出现
    console.log('[Step 6] 等待开场问题...');
    // 等待 AI 消息气泡出现（assistant role 的 rounded-lg 消息）或开场问题加载完成
    await page.waitForSelector('text=AI正在准备开场问题...', { timeout: 5000 }).catch(() => {});
    // 等待加载状态消失，出现 AI 消息
    await page.waitForFunction(
      () => {
        const loadingText = document.querySelector('p.text-gray-600.font-medium');
        return !loadingText || loadingText.textContent !== 'AI正在准备开场问题...';
      },
      { timeout: 120_000 }
    );
    await page.waitForTimeout(3000); // 等待开场问题渲染完成

    const initialState = await getCurrentState(page);
    console.log(`[初始状态] 当前阶段：${initialState}`);
    await page.screenshot({ path: 'e2e/screenshots/05-chat-opening.png' });

    // 断言：初始状态应为"复盘事件"
    expect(initialState).toContain('复盘事件');

    // Step 7-9: 逐轮回答，观察状态变化
    let currentState = initialState;
    let turnCount = 0;
    const maxTurns = 3;

    for (let i = 0; i < maxTurns; i++) {
      turnCount = i + 1;
      console.log(`\n========== 第 ${turnCount} 轮回答 ==========`);

      // 发送回答
      await sendMessageAndWait(page, EXPERT_ANSWERS[i]);
      await page.screenshot({ path: `e2e/screenshots/06-turn-${turnCount}.png` });

      // 检查状态
      const newState = await getCurrentState(page);
      console.log(`[第${turnCount}轮后] 当前阶段：${newState}`);

      // 如果状态已推进，记录并继续（LLM 可能在少于3轮时就建议推进，这是正常的）
      if (newState !== currentState && !newState.includes('复盘事件')) {
        console.log(`[推进] 状态已从"${currentState}"推进到"${newState}"（第${turnCount}轮后）`);
        currentState = newState;

        // 如果已经推进到建构框架或更后面，测试成功
        if (newState.includes('建构框架') || newState.includes('挖掘细节') ||
            newState.includes('识别障碍') || newState.includes('提炼工具') ||
            newState.includes('复述确认')) {
          console.log(`\n✅ 测试通过：状态在第${turnCount}轮后成功推进！`);
          break;
        }
      } else {
        currentState = newState;
      }
    }

    // Step 10: 最终断言
    console.log('\n========== 测试断言 ==========');
    console.log(`最终状态：${currentState}`);
    console.log(`实际进行轮数：${turnCount}`);

    // 核心断言：状态必须已离开"复盘事件"阶段
    const hasAdvanced = !currentState.includes('复盘事件');

    if (hasAdvanced) {
      console.log('✅ 断言通过：状态已成功从"复盘事件"推进');
    } else {
      console.log('❌ 断言失败：状态仍停留在"复盘事件"，兜底机制可能未触发');
    }

    await page.screenshot({ path: 'e2e/screenshots/07-final-state.png' });

    expect(
      hasAdvanced,
      `预期在${maxTurns}轮内从"复盘事件"推进，但实际进行了${turnCount}轮后仍为"${currentState}"`
    ).toBe(true);

    console.log('\n========== 测试完成 ==========\n');
  });

  test('30分钟访谈：验证轮数上限计算正确', async ({ page }) => {
    console.log('\n========== 测试2：30分钟访谈轮数上限验证 ==========');

    // 创建 30 分钟访谈
    await page.goto('/interviews/new');
    await page.getByPlaceholder('例如：新任销售代表的异议处理技巧').fill('销售异议处理技巧');
    await page.getByPlaceholder('描述该经验所在的业务场景和背景...').fill('5年销售经验，擅长处理价格异议');
    await page.getByPlaceholder('例如：资深销售经理').fill('销售主管');
    await page.locator('input[type="number"]').fill('30');

    await page.locator('button[type="submit"]').click();
    await page.waitForURL(/\/interviews\/.*\/blueprint/, { timeout: 60_000 });

    // 等待蓝图并确认
    const generatingLocator = page.locator('text=AI正在生成访谈蓝图');
    if (await generatingLocator.isVisible().catch(() => false)) {
      await generatingLocator.waitFor({ state: 'hidden', timeout: 120_000 });
    }

    await page.getByText('确认蓝图并开始访谈').click();
    await page.waitForURL(/\/interviews\/.*\/chat/, { timeout: 30_000 });

    // 等待开场问题
    await page.waitForSelector('text=AI正在准备开场问题...', { timeout: 5000 }).catch(() => {});
    await page.waitForFunction(
      () => {
        const loadingText = document.querySelector('p.text-gray-600.font-medium');
        return !loadingText || loadingText.textContent !== 'AI正在准备开场问题...';
      },
      { timeout: 120_000 }
    );
    await page.waitForTimeout(3000);

    const initialState = await getCurrentState(page);
    expect(initialState).toContain('复盘事件');
    console.log(`[30分钟访谈] 初始状态：${initialState}`);

    // 30分钟访谈的轮数上限：30/2.5=12总轮数，12/6=2轮/阶段，min(2,3)=2
    // 所以 30 分钟访谈每个阶段最多 2 轮
    const shortAnswer = '我在去年遇到一个客户，第一次见面时我主动询问了他们的业务痛点，通过资金流问题切入，最终成功建立了信任关系。';

    // 第1轮
    await sendMessageAndWait(page, shortAnswer);
    const state1 = await getCurrentState(page);
    console.log(`[30分钟-第1轮后] 状态：${state1}`);

    // 第2轮（此时应触发轮数兜底，因为 30 分钟访谈阶段上限为 2 轮）
    await sendMessageAndWait(page, '后续我安排了项目调研，客户对报告中的优化方案表示认可，同意试点合作。');
    const state2 = await getCurrentState(page);
    console.log(`[30分钟-第2轮后] 状态：${state2}`);

    // 断言：30分钟访谈在 2 轮后应已推进
    const hasAdvanced30 = !state2.includes('复盘事件');
    if (hasAdvanced30) {
      console.log('✅ 30分钟访谈测试通过：2轮后成功推进');
    } else {
      console.log('❌ 30分钟访谈测试失败：2轮后仍未推进');
    }

    await page.screenshot({ path: 'e2e/screenshots/08-30min-final.png' });
    expect(hasAdvanced30, '30分钟访谈应在2轮内推进').toBe(true);
  });
});
