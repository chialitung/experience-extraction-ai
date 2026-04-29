import { test, expect, Page } from '@playwright/test';

/**
 * 经验萃取AI系统 —— 保险产品说明会访谈全流程演示（语音模式）
 *
 * 目标：录制完整的端到端演示视频（MP4）
 * 主题：如何举办成功的保险产品说明会（产说会）
 * 流程：创建访谈 → 生成蓝图 → 语音模式12轮对话 → 完成访谈 → 查看成果 → 生成标准报告
 *
 * 技术方案：
 * - 后端 BaiduRealtimeASRClient 启用 MOCK_TRANSCRIPTION 模式
 * - Playwright 启动 Chrome 时注入 --use-fake-device-for-media-stream
 * - 前端录音、WebSocket、转写流程完全真实，无需修改
 */

// ============ 辅助函数 ============

/** 获取当前阶段文本 */
async function getCurrentState(page: Page): Promise<string> {
  const stateText = await page.locator('text=/当前阶段：/').textContent();
  return stateText?.replace('当前阶段：', '').trim() || '';
}

/** 等待 AI 回复完成（"整理中..."消失） */
async function waitForAiResponse(page: Page, timeoutMs: number = 120_000) {
  // 先等待 AI 加载指示器出现（表示请求已发出）
  await page.waitForSelector('text=AI正在深入分析您的回答', { timeout: 5000 }).catch(() => {
    // 可能已经很快完成，忽略
  });

  // 等待"整理中..."从"下一轮"按钮上消失
  await page.waitForFunction(
    () => {
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        if (btn.textContent?.includes('整理中...')) {
          return false;
        }
      }
      return true;
    },
    { timeout: timeoutMs }
  );
  // 额外等待一下，确保 DOM 更新完成
  await page.waitForTimeout(1500);
}

/** 等待语音转写结果完全出现（FIN_TEXT） */
async function waitForTranscription(page: Page, timeoutMs: number = 180_000) {
  // 等待当前轮次的转录文本出现（通过 "当前轮次（待提交）" 标签定位，避免误匹配历史消息）
  await page.waitForFunction(
    () => {
      const labels = Array.from(document.querySelectorAll('span'));
      const roundLabel = labels.find(s => s.textContent?.includes('当前轮次（待提交）'));
      if (!roundLabel) return false;
      const container = roundLabel.closest('div.flex-col');
      if (!container) return false;
      const textEl = container.querySelector('p.whitespace-pre-wrap');
      return textEl && textEl.textContent && textEl.textContent.length > 10;
    },
    { timeout: timeoutMs }
  );
  // 等待 FIN_TEXT 最终确认（预览消失，确认文本完整）
  await page.waitForFunction(
    () => {
      const labels = Array.from(document.querySelectorAll('span'));
      const roundLabel = labels.find(s => s.textContent?.includes('当前轮次（待提交）'));
      if (!roundLabel) return false;
      const container = roundLabel.closest('div.flex-col');
      if (!container) return false;
      const previewEl = container.querySelector('p.opacity-60');
      return !previewEl || previewEl.textContent === '';
    },
    { timeout: 5000 }
  );
}

/** 等待语音识别连接成功 */
async function waitForTranscriptionConnected(page: Page, timeoutMs: number = 15_000) {
  await page.waitForSelector('text=实时语音识别已连接', { timeout: timeoutMs });
}

// ============ 测试主体 ============

test.describe('保险产品说明会访谈 —— 语音模式全流程演示', () => {
  test('完整访谈流程 with 语音输入并录屏', async ({ page }) => {
    console.log('\n========== 演示开始 ==========');
    console.log('主题：如何举办成功的保险产品说明会（产说会）');
    console.log('预计轮次：8 轮（覆盖 6 个访谈阶段）');
    console.log('视频将保存至 test-results/ 目录\n');

    // ==================== Phase 1: 创建访谈 ====================

    // Step 1: 访问首页
    console.log('[Step 1] 访问首页');
    await page.goto('/');
    console.log('[完成] 已访问首页');

    await expect(page.locator('h1.text-5xl')).toContainText('经验萃取AI');
    await page.screenshot({ path: 'e2e/screenshots/voice_01_homepage.png' });

    // Step 2: 点击创建新访谈
    console.log('[Step 2] 点击"开始新的萃取访谈"');
    await page.getByText('开始新的萃取访谈').click();
    await expect(page.getByText('创建新访谈')).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/voice_02_create_page.png' });

    // Step 3: 填写表单
    console.log('[Step 3] 填写访谈表单');
    await page.getByPlaceholder('例如：新任销售代表的异议处理技巧')
      .fill('如何举办成功的保险产品说明会（产说会）');
    await page.getByPlaceholder('描述该经验所在的业务场景和背景...')
      .fill('拥有10年保险行业经验，擅长组织大型保险产品说明会，年均举办50场以上，单场最高成交率达35%');
    await page.getByPlaceholder('例如：资深销售经理')
      .fill('资深保险营销总监');

    // 确保时长为 10 分钟
    const durationInput = page.locator('input[type="number"]');
    await durationInput.fill('10');

    await page.screenshot({ path: 'e2e/screenshots/voice_03_form_filled.png' });
    console.log('[暂停] 等待 2 秒，展示已填写的表单内容');
    await page.waitForTimeout(2000);

    // Step 4: 提交表单，等待蓝图
    console.log('[Step 4] 提交表单，等待蓝图生成...');
    await page.click('button[type="submit"]');

    await page.waitForURL(/\/interviews\/.*\/blueprint/, { timeout: 60_000 });
    await expect(page.locator('text=访谈蓝图')).toBeVisible({ timeout: 120_000 });

    // 等待蓝图生成完成
    const generatingLocator = page.locator('text=AI正在生成访谈蓝图');
    if (await generatingLocator.isVisible().catch(() => false)) {
      console.log('[等待] 蓝图生成中...');
      await generatingLocator.waitFor({ state: 'hidden', timeout: 120_000 });
    }

    await page.screenshot({ path: 'e2e/screenshots/voice_04_blueprint.png' });
    console.log('[完成] 蓝图生成完毕');

    // Step 5: 确认蓝图并开始访谈
    console.log('[Step 5] 确认蓝图，进入访谈');
    const confirmBtn = page.getByText('确认蓝图并开始访谈');
    await confirmBtn.click();

    // 处理录音设置弹窗（如弹出）
    const recordingModal = page.locator('text=录音设置');
    if (await recordingModal.isVisible().catch(() => false)) {
      console.log('[处理] 关闭录音设置弹窗');
      await page.getByRole('button', { name: '开始访谈', exact: true }).click();
    }

    // 等待跳转到聊天页面
    await page.waitForURL(/\/interviews\/.*\/chat/, { timeout: 30_000 });
    await expect(page.getByText('完成访谈')).toBeVisible({ timeout: 30_000 });
    console.log('[完成] 已进入聊天页面');

    // Step 6: 等待开场问题出现
    console.log('[Step 6] 等待开场问题...');
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
    console.log(`[初始状态] 当前阶段：${initialState}`);
    await page.screenshot({ path: 'e2e/screenshots/voice_05_chat_opening.png' });

    // ==================== Phase 2: 语音模式对话（12轮）====================

    // Step 7: 开启录音模式
    console.log('[Step 7] 开启录音模式');
    // 查找录音按钮（匹配"录音"或"录音中"）
    const recordingBtn = page.locator('button').filter({ hasText: /录音/ }).first();
    const recordingBtnText = await recordingBtn.textContent().catch(() => '');
    if (recordingBtnText.includes('录音') && !recordingBtnText.includes('录音中')) {
      await recordingBtn.click();
      console.log('[动作] 点击录音按钮开启录音');
    }

    // 等待录音中状态出现
    await expect(page.locator('text=录音中')).toBeVisible({ timeout: 10_000 });
    console.log('[完成] 录音模式已开启');

    // 等待实时语音识别连接
    console.log('[等待] 等待实时语音识别连接...');
    await waitForTranscriptionConnected(page, 15_000);
    console.log('[完成] 实时语音识别已连接');
    await page.screenshot({ path: 'e2e/screenshots/voice_06_recording_started.png' });

    // 8 轮对话循环（部分阶段多轮深挖）
    const maxRounds = 8;
    let currentState = initialState;

    for (let round = 1; round <= maxRounds; round++) {
      console.log(`\n========== 第 ${round} 轮语音输入 ==========`);

      // 等待 Mock ASR 返回转写结果
      console.log(`[第${round}轮] 等待语音转写结果...`);
      await waitForTranscription(page, 180_000);

      // 获取转写文本长度
      const transcriptLength = await page.evaluate(() => {
        const el = document.querySelector('p.whitespace-pre-wrap');
        return el?.textContent?.length || 0;
      });
      console.log(`[第${round}轮] 转写完成，共 ${transcriptLength} 字`);
      await page.screenshot({ path: `e2e/screenshots/voice_07_turn_${round}_transcribed.png` });

      // 点击"下一轮"按钮
      console.log(`[第${round}轮] 点击"下一轮"...`);
      const nextRoundBtn = page.getByText('下一轮');
      await nextRoundBtn.click();

      // 等待 AI 回复完成
      console.log(`[第${round}轮] 等待 AI 回复...`);
      await waitForAiResponse(page);

      // 检查当前阶段
      const newState = await getCurrentState(page);
      if (newState !== currentState) {
        console.log(`[第${round}轮] ✅ 阶段推进："${currentState}" → "${newState}"`);
        currentState = newState;
      } else {
        console.log(`[第${round}轮] 当前阶段：${newState}`);
      }
      await page.screenshot({ path: `e2e/screenshots/voice_08_turn_${round}_completed.png` });

      // 如果已经到达"已完成"或"复述确认"且是最后一轮，提前结束
      if (currentState.includes('已完成') || currentState.includes('completed')) {
        console.log(`[第${round}轮] 访谈已完成，提前结束对话`);
        break;
      }

      // 如果不是最后一轮，重新开启录音（下一轮会自动开启，因为 recording.isActive 仍为 true）
      const isRecordingActive = await page.locator('text=录音中').isVisible().catch(() => false);
      if (!isRecordingActive && round < maxRounds) {
        console.log(`[第${round}轮] 重新开启录音`);
        const recBtn = page.locator('button').filter({ hasText: /^录音$/ }).first();
        if (await recBtn.isVisible().catch(() => false)) {
          await recBtn.click();
          await expect(page.locator('text=录音中')).toBeVisible({ timeout: 10_000 });
        }
      }
    }

    console.log(`\n========== 对话阶段结束 ==========`);
    console.log(`最终阶段：${currentState}`);

    // ==================== Phase 3: 完成与查看成果 ====================

    // Step 23: 完成访谈
    console.log('\n[Step 23] 点击"完成访谈"');
    const completeBtn = page.getByText('完成访谈');
    await completeBtn.click();

    // 等待跳转到输出页面
    await page.waitForURL(/\/interviews\/.*\/output/, { timeout: 60_000 });
    await expect(page.locator('text=访谈素材包').first()).toBeVisible({ timeout: 30_000 });
    console.log('[完成] 已跳转至萃取成果页面');
    await page.screenshot({ path: 'e2e/screenshots/voice_09_output_overview.png' });

    // Step 24-25: 浏览各成果标签
    console.log('[Step 24-25] 浏览各成果标签');
    const tabs = [
      { name: '话术卡', id: 'script_card' },
      { name: '检查表', id: 'checklist' },
      { name: '流程图', id: 'flowchart' },
      { name: '学习卡', id: 'learning_card' },
      { name: '案例', id: 'case_study' },
    ];

    for (const tab of tabs) {
      const tabBtn = page.getByText(tab.name).first();
      if (await tabBtn.isVisible().catch(() => false)) {
        await tabBtn.click();
        await page.waitForTimeout(2000);
        await page.screenshot({ path: `e2e/screenshots/voice_10_output_${tab.id}.png` });
        console.log(`[浏览] ${tab.name}`);
      }
    }

    // Step 26-28: 生成标准报告
    console.log('\n[Step 26-28] 生成标准报告');
    const reportLink = page.getByText('经验分析报告').first();
    if (await reportLink.isVisible().catch(() => false)) {
      await reportLink.click();
      await page.waitForTimeout(2000);
    }

    // 点击生成标准版报告
    const generateBtn = page.getByRole('button', { name: /生成.*报告/ }).first();
    if (await generateBtn.isVisible().catch(() => false)) {
      await generateBtn.click();
      console.log('[等待] 报告生成中...（最长等待10分钟）');

      // 等待报告内容加载：先等"生成中"状态消失，再等报告标题出现
      await page.waitForFunction(
        () => {
          const btn = document.querySelector('button');
          return !btn || !btn.textContent?.includes('生成中');
        },
        { timeout: 600_000 }
      );

      // 报告生成完成后，等待核心内容出现
      await page.waitForSelector('text=/执行摘要|核心发现|分析结论/', { timeout: 60_000 });
      console.log('[完成] 标准报告已生成');
    }

    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'e2e/screenshots/voice_11_report_generated.png' });

    // Step 29: 查看报告各关键章节
    console.log('[Step 29] 查看报告各关键章节');

    // 先回到顶部
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(1000);

    // 获取报告中的所有章节标题（通常是 h2 或 h3）
    const chapterSelectors = [
      'text=/执行摘要|核心发现/',
      'text=/事件复盘|案例背景|经验场景/',
      'text=/框架建构|方法模型|核心方法/',
      'text=/细节挖掘|关键细节|操作要点/',
      'text=/障碍识别|常见挑战|难点分析/',
      'text=/工具提炼|实用工具|成果输出/',
      'text=/行动建议|落地建议|实践指导/',
    ];

    let chapterIndex = 0;
    for (const selector of chapterSelectors) {
      const heading = page.locator(selector).first();
      if (await heading.isVisible().catch(() => false)) {
        await heading.scrollIntoViewIfNeeded();
        await page.waitForTimeout(1500);
        await page.screenshot({ path: `e2e/screenshots/voice_11b_report_chapter_${chapterIndex}.png` });
        console.log(`[报告章节] 已查看: ${await heading.textContent()}`);
        chapterIndex++;
      }
    }

    // 回到顶部，展示完整报告概览
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'e2e/screenshots/voice_11c_report_overview.png' });

    // Step 30: 滚动浏览报告全貌（从顶到底）
    console.log('[Step 30] 滚动浏览报告全貌');
    for (const pos of [0.25, 0.5, 0.75, 1.0]) {
      await page.evaluate((p) => window.scrollTo(0, document.body.scrollHeight * p), pos);
      await page.waitForTimeout(2000);
      await page.screenshot({ path: `e2e/screenshots/voice_12_report_scroll_${Math.round(pos * 100)}.png` });
    }

    // 最终截图
    await page.screenshot({ path: 'e2e/screenshots/voice_13_final.png' });

    console.log('\n========== 演示完成 ==========');
    console.log('视频文件请查看 test-results/ 目录');
    console.log('可使用 ffmpeg 转换为 MP4 格式');
  });
});
