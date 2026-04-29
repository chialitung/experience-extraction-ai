const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:5173';
const SCREENSHOT_DIR = path.join(__dirname, 'e2e_screenshots');

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

let screenshotIndex = 0;
async function screenshot(page, name) {
  screenshotIndex++;
  const filePath = path.join(SCREENSHOT_DIR, `${String(screenshotIndex).padStart(2, '0')}_${name}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  console.log(`[截图] ${filePath}`);
  return filePath;
}

const bugs = [];
function recordBug(severity, step, description, detail = '') {
  bugs.push({ severity, step, description, detail, time: new Date().toISOString() });
  console.log(`[BUG][${severity}] 步骤: ${step} | ${description}`);
  if (detail) console.log(`  详情: ${detail}`);
}

const ANSWERS = [
  "我是李明，在一家软件公司担任高级销售经理，主要负责大客户的拓展和维护工作。最近我成功签约了一个非常重要的客户——某大型金融机构的信息化改造项目。这个客户我们跟进了将近一年，期间遇到了很多阻力和挑战。最初接触时，客户对我们公司的品牌认知度不高，而且已经有几家竞争对手在接触他们。",
  "客户的基本情况是：这是一家省级城商行，正在推进数字化转型，需要一套完整的核心业务系统升级方案。初次接触是通过行业峰会认识的，当时是他们的信息技术部负责人参会。我主动交换了名片，并在会后一周内发送了针对性的行业解决方案白皮书。第一次正式拜访是在一个月之后，我带上了我们的售前架构师，针对他们现有的系统痛点做了初步的诊断分析。",
  "这个案例发生在2025年3月到2026年1月期间。第一次拜访后，客户反应比较冷淡，只是说会考虑。但我注意到他们在讨论中提到了对数据迁移风险的担忧。第二次拜访前，我专门准备了一份详细的数据迁移风险评估报告，还安排他们参观了我们另一个已经成功实施类似项目的银行客户。这次拜访后，客户的态度明显转变，开始让我们参与他们的需求调研。",
  "关键的转折点出现在第二次拜访之后。客户IT负责人私下告诉我，他们的行长对项目的稳定性要求非常高，因为核心业务系统一旦出问题会影响全行的日常运营。我意识到这是一个非常关键的信息，于是立即调整策略，在第三次拜访中重点展示了我们系统的容灾备份方案和高可用架构设计。同时，我还安排了一个惊喜环节——让我们的技术总监通过视频连线，与他们的技术团队进行了长达两个小时的深度技术交流。",
  "回顾整个过程，我认为成功的关键因素有三个：第一，精准的需求洞察。我在第一次拜访后就意识到，单纯讲产品功能是没有用的，必须深入到客户的业务场景中去理解他们的真实痛点。第二，信任的建立是一个渐进的过程。我从行业峰会接触，到白皮书跟进，再到现场诊断、同行参观，每一步都在积累信任。第三，技术深度的展示。对于金融机构来说，技术架构的稳定性和安全性是他们最关心的。",
  "这个经验可以提炼为一个'三阶信任建立模型'：第一阶段是'认知建立'——通过行业活动和内容输出，让客户了解你的专业能力和行业经验。第二阶段是'信心强化'——通过案例参观、第三方背书、风险评估等方式，消除客户的顾虑。第三阶段是'深度共鸣'——邀请技术专家进行深度交流，让客户感受到你不仅仅是卖产品，而是真正理解他们的业务和技术挑战。",
  "在这个过程中，我遇到的最大障碍是客户的'沉默期'。第一次拜访后，有将近两个月的时间客户没有任何回应。我当时非常焦虑，甚至怀疑这个项目是不是已经没戏了。我的应对策略是：不直接追问项目进展，而是每隔两周发送一封行业洞察邮件，分享一些与他们业务相关的最新技术趋势或同业案例。这样既保持了联系，又不会给对方压力。",
  "还有一个隐性的障碍是决策链的复杂性。表面上跟我们对接的是IT部门，但真正拍板的是行长和分管副行长。我花了很长时间才搞清楚这个决策链。我的解决方法是：在跟IT部门建立良好关系后，通过他们了解到行长的关注重点——原来是上一任供应商的服务响应速度太慢，影响了业务连续性。于是我在方案中特别强调了我们的7×24小时专属服务团队和30分钟响应承诺。",
  "基于这个经验，我总结出几个实用的工具和方法：工具一：'痛点地图'。在第一次拜访后，我会绘制一张客户的痛点地图，列出他们可能的顾虑点，然后在后续的每次接触中有针对性地消除这些顾虑。工具二：'信任积累清单'。我会记录每一次与客户的互动，评估信任度从1到10的变化，确保每次互动都能提升至少1分。工具三：'决策链图谱'。通过观察和询问，绘制出客户的决策链，了解每个决策者的关注点和影响力。",
  "如果要给刚入行的新人一个建议，我会说：不要急于推销产品，先学会倾听和理解。在这个案例中，如果我第一次拜访就大讲我们的系统有多好，客户可能根本不会给我第二次机会。真正让我赢得这个项目的是我对他们业务痛点的深刻理解，以及我展现出的专业性和耐心。另外，要学会利用公司的资源。我多次邀请技术专家参与，这不仅展示了我们的技术实力，也让客户感受到我们对这个项目的重视程度。",
  "总结一下，这个案例的核心经验是：大客户销售不是百米冲刺，而是马拉松。你需要有耐心，有策略，更要有真正的专业能力。信任的建立需要时间，但一旦建立，就会非常稳固。我的'三阶信任建立模型'——认知建立、信心强化、深度共鸣——适用于绝大多数B2B大客户销售场景。关键是要根据客户的具体情况灵活调整每个阶段的时间和节奏。最后，永远不要低估技术深度的价值。",
];

async function waitForSelector(page, selector, timeout = 10000) {
  try {
    await page.waitForSelector(selector, { timeout });
    return true;
  } catch (e) {
    return false;
  }
}

async function waitForText(page, text, timeout = 10000) {
  try {
    await page.waitForFunction(
      (t) => document.body.innerText.includes(t),
      text,
      { timeout }
    );
    return true;
  } catch (e) {
    return false;
  }
}

async function safeFill(page, selector, text) {
  try {
    const el = await page.$(selector);
    if (el) {
      await el.fill(text);
      return true;
    }
  } catch (e) {
    console.log(`填充失败: ${selector} - ${e.message}`);
  }
  return false;
}

async function safeClickByText(page, text, timeout = 5000) {
  try {
    const btn = await page.locator(`button:has-text("${text}")`).first();
    await btn.waitFor({ timeout });
    await btn.click();
    return true;
  } catch (e) {
    console.log(`点击失败: "${text}" - ${e.message}`);
    return false;
  }
}

(async () => {
  console.log('=== 经验萃取AI系统 E2E 全流程测试 ===');
  console.log(`截图目录: ${SCREENSHOT_DIR}`);

  const browser = await chromium.launch({
    headless: true,
    executablePath: 'D:\\Program Files\\chrome-headless-shell-win64\\chrome-headless-shell.exe',
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // 设置默认超时
  page.setDefaultTimeout(30000);

  try {
    // ===== Step 1: 创建访谈 =====
    console.log('\n--- Step 1: 创建访谈 ---');
    await page.goto(`${BASE_URL}/interviews/new`);
    await page.waitForTimeout(2000);
    await screenshot(page, '01_create_page');

    // 填写主题（第一个text input）
    const inputs = await page.$$('input[type="text"]');
    if (inputs.length >= 1) {
      await inputs[0].fill('大客户销售的信任建立技巧——以金融行业为例');
    } else {
      recordBug('blocking', '创建访谈', '未找到主题输入框');
    }

    // 填写背景（textarea）
    const textareas = await page.$$('textarea');
    if (textareas.length >= 1) {
      await textareas[0].fill('某省级城商行核心业务系统升级项目，历时10个月最终签约。');
    }

    // 填写专家角色（第二个text input）
    if (inputs.length >= 2) {
      await inputs[1].fill('资深销售经理');
    }

    await screenshot(page, '02_form_filled');

    // 点击创建按钮
    const createBtn = await page.$('button[type="submit"]');
    if (createBtn) {
      await createBtn.click();
      console.log('  已点击创建按钮');
    } else {
      recordBug('blocking', '创建访谈', '未找到创建按钮');
    }

    // 等待页面跳转（蓝图页或加载中）
    await page.waitForTimeout(5000);
    await screenshot(page, '03_after_create_click');

    let currentUrl = page.url();
    console.log(`当前URL: ${currentUrl}`);

    // 如果还在创建页，再等一下
    if (currentUrl.includes('/new')) {
      await page.waitForTimeout(8000);
      currentUrl = page.url();
      console.log(`等待后URL: ${currentUrl}`);
    }

    // 提前提取访谈ID
    let interviewId = null;
    const idMatch = currentUrl.match(/\/interviews\/([^/]+)/);
    if (idMatch) {
      interviewId = idMatch[1];
      console.log(`  提取到访谈ID: ${interviewId}`);
    }

    // ===== Step 2: 蓝图页 =====
    console.log('\n--- Step 2: 蓝图页 ---');
    await screenshot(page, '04_blueprint_page');

    // 等待蓝图内容加载（判断是否有"萃取主题"或"访谈蓝图"）
    const hasBlueprint = await waitForText(page, '萃取主题', 30000);
    if (!hasBlueprint) {
      recordBug('blocking', '蓝图页', '页面未显示"萃取主题"文本');
    }

    await screenshot(page, '05_blueprint_loaded');

    // 点击确认蓝图按钮
    const confirmOk = await safeClickByText(page, '确认蓝图并开始访谈', 5000);
    if (!confirmOk) {
      recordBug('blocking', '蓝图页', '未找到确认蓝图并开始访谈按钮');
    }

    await page.waitForTimeout(2000);
    await screenshot(page, '06_after_blueprint_confirm');

    currentUrl = page.url();
    console.log(`确认蓝图后URL: ${currentUrl}`);

    // 处理录音设置弹窗
    if (await waitForText(page, '录音设置', 5000)) {
      console.log('  检测到录音设置弹窗');
      await page.waitForTimeout(1000); // 等弹窗动画完成
      // 关闭录音开关（如果有的话）—— 找切换开关并关闭
      const toggle = await page.$('button[role="switch"], .relative.w-12.h-7');
      if (toggle) {
        await toggle.click();
        await page.waitForTimeout(800);
      }
      // 点击开始访谈（弹窗内按钮）
      try {
        // 在弹窗内找开始访谈按钮
        const startBtn = await page.locator('div.bg-white >> button:has-text("开始访谈")').first();
        await startBtn.click();
        console.log('  已点击开始访谈');
        await page.waitForTimeout(3000);
      } catch (e) {
        console.log(`  点击开始访谈失败: ${e.message}`);
      }
      // 兜底：如果URL没变，直接跳转chat页
      currentUrl = page.url();
      if (!currentUrl.includes('/chat') && interviewId) {
        console.log('  页面未跳转，直接导航到访谈页');
        await page.goto(`${BASE_URL}/interviews/${interviewId}/chat`);
        await page.waitForTimeout(3000);
      }
      await screenshot(page, '07_after_start_interview');
    }

    // ===== Step 3: 访谈页 =====
    console.log('\n--- Step 3: 访谈页 ---');
    currentUrl = page.url();
    console.log(`访谈页URL: ${currentUrl}`);

    if (!currentUrl.includes('/chat')) {
      // 等待跳转
      await page.waitForFunction(() => location.pathname.includes('/chat'), {}, { timeout: 15000 });
      currentUrl = page.url();
      console.log(`等待跳转后URL: ${currentUrl}`);
    }

    await screenshot(page, '08_chat_page');

    // 等待AI开场白或消息出现
    console.log('  等待AI开场白...');
    const hasMessage = await waitForSelector(page, '[class*="rounded-lg"]', 30000);
    await page.waitForTimeout(3000);
    await screenshot(page, '09_chat_loaded');

    // 模拟多轮回答（非录音模式：直接发送消息）
    const maxRounds = Math.min(ANSWERS.length, 12);
    for (let round = 0; round < maxRounds; round++) {
      console.log(`\n--- 第 ${round + 1} 轮回答 ---`);

      // 等待输入框可用
      const inputReady = await waitForSelector(page, 'textarea:not([disabled])', 10000);
      if (!inputReady) {
        recordBug('blocking', `第${round + 1}轮`, '输入框未就绪或不可用');
        await screenshot(page, `10_round_${round + 1}_input_disabled`);
        break;
      }

      // 填写回答
      const textareas = await page.$$('textarea');
      if (textareas.length === 0) {
        recordBug('blocking', `第${round + 1}轮`, '未找到textarea输入框');
        break;
      }
      const inputBox = textareas[textareas.length - 1]; // 最后一个textarea通常是输入框
      await inputBox.fill(ANSWERS[round]);
      await page.waitForTimeout(500);
      await screenshot(page, `10_round_${round + 1}_input_filled`);

      // 发送消息：在textarea中按Enter（比找按钮更可靠）
      try {
        await inputBox.press('Enter');
        console.log(`  已发送（按Enter）`);
      } catch (e) {
        recordBug('blocking', `第${round + 1}轮`, '发送消息失败', e.message);
        await screenshot(page, `10_round_${round + 1}_send_failed`);
        break;
      }

      // 等待AI回复（等待加载状态消失或新消息出现）
      console.log(`  等待AI回复...`);
      await page.waitForTimeout(5000);

      // 检查是否出现错误
      const pageText = await page.evaluate(() => document.body.innerText);
      if (pageText.includes('500') && pageText.includes('错误')) {
        recordBug('blocking', `第${round + 1}轮`, '页面出现500错误', pageText.slice(0, 300));
        await screenshot(page, `10_round_${round + 1}_error`);
        break;
      }

      // 等待AI思考完成（最多60秒）
      let waited = 0;
      const maxWait = 60;
      while (waited < maxWait) {
        const isLoading = await page.evaluate(() => {
          const text = document.body.innerText;
          return text.includes('AI正在深入分析') || text.includes('AI正在思考');
        });
        if (!isLoading) break;
        await page.waitForTimeout(2000);
        waited += 2;
      }
      console.log(`  AI回复等待了 ${waited} 秒`);
      await screenshot(page, `10_round_${round + 1}_completed`);

      // 检查状态推进（看header中的阶段文本）
      const stateText = await page.evaluate(() => {
        const el = document.querySelector('h2.font-semibold');
        return el ? el.innerText : '';
      });
      console.log(`  当前页面主题: ${stateText}`);
    }

    // ===== Step 4: 结束访谈 =====
    console.log('\n--- Step 4: 结束访谈 ---');
    const completeOk = await safeClickByText(page, '完成访谈', 5000);
    if (completeOk) {
      console.log('  已点击完成访谈');
      await page.waitForTimeout(8000);
    } else {
      console.log('  未找到完成访谈按钮，尝试直接访问报告页');
    }
    await screenshot(page, '11_after_complete');

    // 如果之前没有提取到ID，再试一次
    if (!interviewId) {
      const interviewIdMatch = page.url().match(/\/interviews\/([^/]+)/);
      interviewId = interviewIdMatch ? interviewIdMatch[1] : null;
    }
    console.log(`  访谈ID: ${interviewId}`);

    if (!interviewId) {
      recordBug('blocking', '结束访谈', '无法从URL提取访谈ID');
    }

    // ===== Step 5: 报告页 =====
    console.log('\n--- Step 5: 报告页 ---');
    if (interviewId) {
      await page.goto(`${BASE_URL}/interviews/${interviewId}/report`);
      await page.waitForTimeout(4000);
      await screenshot(page, '12_report_page');

      const reportText = await page.evaluate(() => document.body.innerText);
      if (reportText.includes('分析报告') || reportText.includes('经验') || reportText.includes('萃取')) {
        console.log('  报告页有内容');
      } else {
        recordBug('non-blocking', '报告页', '报告页内容为空或缺少关键文本');
      }

      // 测试三档深度切换（先点击下拉触发器，再点击选项）
      const depthOptions = [
        { key: 'brief', label: '简要版' },
        { key: 'standard', label: '标准版' },
        { key: 'deep', label: '深度版' },
      ];

      for (const opt of depthOptions) {
        try {
          // 点击下拉触发按钮打开菜单
          const dropdownTrigger = await page.$('.depth-dropdown button');
          if (dropdownTrigger) {
            await dropdownTrigger.click();
            await page.waitForTimeout(800);

            // 点击下拉选项
            const optionBtn = await page.locator(`.depth-dropdown button:has-text("${opt.label}")`).first();
            await optionBtn.waitFor({ timeout: 3000 });
            await optionBtn.click();
            await page.waitForTimeout(2500);
            console.log(`  已切换至: ${opt.label}`);
          } else {
            recordBug('non-blocking', '报告页深度切换', `未找到深度下拉菜单触发器`, `尝试切换至 ${opt.label}`);
          }
        } catch (e) {
          recordBug('non-blocking', '报告页深度切换', `切换 ${opt.label} 失败`, e.message);
        }
      }
      await screenshot(page, '13_report_depth_switch');

      // 访问素材页
      await page.goto(`${BASE_URL}/interviews/${interviewId}/output`);
      await page.waitForTimeout(4000);
      await screenshot(page, '14_output_page');

      const outputText = await page.evaluate(() => document.body.innerText);
      if (outputText.includes('话术卡') || outputText.includes('检查表') || outputText.includes('流程图')) {
        console.log('  素材页有内容');
      } else {
        recordBug('non-blocking', '素材页', '素材页内容为空或缺少关键文本');
      }
    }

  } catch (err) {
    recordBug('blocking', '全局', '测试脚本异常', err.stack || err.message);
    await screenshot(page, '99_fatal_error');
  } finally {
    await screenshot(page, '99_final_state');
    await browser.close();
  }

  // ===== 生成测试报告 =====
  console.log('\n=== 测试完成 ===');
  console.log(`总BUG数: ${bugs.length}`);
  console.log(`阻塞BUG: ${bugs.filter(b => b.severity === 'blocking').length}`);
  console.log(`非阻塞BUG: ${bugs.filter(b => b.severity === 'non-blocking').length}`);

  const reportPath = path.join(__dirname, 'e2e_test_report.md');
  const reportContent = `# 经验萃取AI系统 - E2E全流程测试报告

**测试时间**: ${new Date().toLocaleString('zh-CN')}
**前端地址**: ${BASE_URL}

## 测试概览

| 指标 | 数值 |
|------|------|
| 总截图数 | ${screenshotIndex} |
| BUG总数 | ${bugs.length} |
| 阻塞BUG | ${bugs.filter(b => b.severity === 'blocking').length} |
| 非阻塞BUG | ${bugs.filter(b => b.severity === 'non-blocking').length} |

## BUG清单

${bugs.map((b, i) => `### BUG-${i + 1} [${b.severity.toUpperCase()}]
- **步骤**: ${b.step}
- **描述**: ${b.description}
- **时间**: ${b.time}
${b.detail ? `- **详情**: ${b.detail}` : ''}
`).join('\n')}

## 截图文件

${fs.readdirSync(SCREENSHOT_DIR).map(f => `- ${f}`).join('\n')}

---
*报告由浏览器自动化测试脚本生成*
`;

  fs.writeFileSync(reportPath, reportContent);
  console.log(`\n报告已保存: ${reportPath}`);

  const blockingBugs = bugs.filter(b => b.severity === 'blocking');
  if (blockingBugs.length > 0) {
    console.log('\n⚠️ 发现阻塞BUG，需要修复:');
    blockingBugs.forEach(b => console.log(`  - [${b.step}] ${b.description}`));
    process.exitCode = 1;
  } else {
    console.log('\n✅ 未发现阻塞BUG');
  }
})();
