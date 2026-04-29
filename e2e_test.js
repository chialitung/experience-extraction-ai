const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:5173';
const API_URL = 'http://localhost:8000';
const SCREENSHOT_DIR = path.join(__dirname, 'e2e_screenshots');

// 确保截图目录存在
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
  // 阶段1: 复盘事件
  "我是李明，在一家软件公司担任高级销售经理，主要负责大客户的拓展和维护工作。\n\n最近我成功签约了一个非常重要的客户——某大型金融机构的信息化改造项目。这个客户我们跟进了将近一年，期间遇到了很多阻力和挑战。\n\n最初接触时，客户对我们公司的品牌认知度不高，而且已经有几家竞争对手在接触他们。我通过三次关键的拜访，逐步建立了信任关系，最终成功拿下了这个价值800万的项目。",
  "客户的基本情况是：这是一家省级城商行，正在推进数字化转型，需要一套完整的核心业务系统升级方案。\n\n初次接触是通过行业峰会认识的，当时是他们的信息技术部负责人参会。我主动交换了名片，并在会后一周内发送了针对性的行业解决方案白皮书。\n\n第一次正式拜访是在一个月之后，我带上了我们的售前架构师，针对他们现有的系统痛点做了初步的诊断分析。",
  // 阶段2: 细节探勘
  "这个案例发生在2025年3月到2026年1月期间。\n\n第一次拜访后，客户反应比较冷淡，只是说会考虑。但我注意到他们在讨论中提到了对数据迁移风险的担忧。\n\n第二次拜访前，我专门准备了一份详细的数据迁移风险评估报告，还安排他们参观了我们另一个已经成功实施类似项目的银行客户。这次拜访后，客户的态度明显转变，开始让我们参与他们的需求调研。\n\n第三次拜访是方案汇报，我邀请了我们的首席架构师一起出席，针对他们的核心业务场景做了定制化的演示。",
  "关键的转折点出现在第二次拜访之后。\n\n客户IT负责人私下告诉我，他们的行长对项目的稳定性要求非常高，因为核心业务系统一旦出问题会影响全行的日常运营。\n\n我意识到这是一个非常关键的信息，于是立即调整策略，在第三次拜访中重点展示了我们系统的容灾备份方案和高可用架构设计。同时，我还安排了一个惊喜环节——让我们的技术总监通过视频连线，与他们的技术团队进行了长达两个小时的深度技术交流。",
  // 阶段3: 框架建构
  "回顾整个过程，我认为成功的关键因素有三个：\n\n第一，精准的需求洞察。我在第一次拜访后就意识到，单纯讲产品功能是没有用的，必须深入到客户的业务场景中去理解他们的真实痛点。\n\n第二，信任的建立是一个渐进的过程。我从行业峰会接触，到白皮书跟进，再到现场诊断、同行参观，每一步都在积累信任。特别是安排参观已实施客户，这种第三方背书的效果非常好。\n\n第三，技术深度的展示。对于金融机构来说，技术架构的稳定性和安全性是他们最关心的。我们在第三次拜访中展示的高可用方案和容灾设计，直接击中了他们的核心关切。",
  "这个经验可以提炼为一个'三阶信任建立模型'：\n\n第一阶段是'认知建立'——通过行业活动和内容输出，让客户了解你的专业能力和行业经验。\n\n第二阶段是'信心强化'——通过案例参观、第三方背书、风险评估等方式，消除客户的顾虑。\n\n第三阶段是'深度共鸣'——邀请技术专家进行深度交流，让客户感受到你不仅仅是卖产品，而是真正理解他们的业务和技术挑战。\n\n这个模型的核心在于：每一次接触都要比上一次更深入，每一次都要给客户带来新的价值。",
  // 阶段4: 障碍识别
  "在这个过程中，我遇到的最大障碍是客户的'沉默期'。\n\n第一次拜访后，有将近两个月的时间客户没有任何回应。我当时非常焦虑，甚至怀疑这个项目是不是已经没戏了。\n\n我的应对策略是：不直接追问项目进展，而是每隔两周发送一封行业洞察邮件，分享一些与他们业务相关的最新技术趋势或同业案例。这样既保持了联系，又不会给对方压力。\n\n后来客户告诉我，那段时间他们内部正在进行预算审批流程，确实不方便对外沟通。我的行业邮件让他们觉得我是一个有价值的合作伙伴，而不是单纯的推销员。",
  "还有一个隐性的障碍是决策链的复杂性。\n\n表面上跟我们对接的是IT部门，但真正拍板的是行长和分管副行长。我花了很长时间才搞清楚这个决策链。\n\n我的解决方法是：在跟IT部门建立良好关系后，通过他们了解到行长的关注重点——原来是上一任供应商的服务响应速度太慢，影响了业务连续性。于是我在方案中特别强调了我们的7×24小时专属服务团队和30分钟响应承诺。这个点直接打动了行长。",
  // 阶段5: 工具萃取
  "基于这个经验，我总结出几个实用的工具和方法：\n\n工具一：'痛点地图'。在第一次拜访后，我会绘制一张客户的痛点地图，列出他们可能的顾虑点，然后在后续的每次接触中有针对性地消除这些顾虑。\n\n工具二：'信任积累清单'。我会记录每一次与客户的互动，评估信任度从1到10的变化，确保每次互动都能提升至少1分。\n\n工具三：'决策链图谱'。通过观察和询问，绘制出客户的决策链，了解每个决策者的关注点和影响力，然后制定针对性的沟通策略。\n\n工具四：'价值增量原则'。每次与客户接触前，我都会问自己：这次见面我能为客户提供什么新的价值？如果不能回答这个问题，我就不会约见面。",
  "如果要给刚入行的新人一个建议，我会说：不要急于推销产品，先学会倾听和理解。\n\n在这个案例中，如果我第一次拜访就大讲我们的系统有多好，客户可能根本不会给我第二次机会。真正让我赢得这个项目的是我对他们业务痛点的深刻理解，以及我展现出的专业性和耐心。\n\n另外，要学会利用公司的资源。我多次邀请技术专家参与，这不仅展示了我们的技术实力，也让客户感受到我们对这个项目的重视程度。一个人的力量是有限的，但一个团队的力量是无限的。",
  // 阶段6: 确认
  "总结一下，这个案例的核心经验是：大客户销售不是百米冲刺，而是马拉松。\n\n你需要有耐心，有策略，更要有真正的专业能力。信任的建立需要时间，但一旦建立，就会非常稳固。\n\n我的'三阶信任建立模型'——认知建立、信心强化、深度共鸣——适用于绝大多数B2B大客户销售场景。关键是要根据客户的具体情况灵活调整每个阶段的时间和节奏。\n\n最后，永远不要低估技术深度的价值。对于金融、医疗、制造等行业的客户来说，技术方案的安全性和稳定性往往比价格更重要。"
];

async function waitFor(page, selector, timeout = 10000) {
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

async function safeClick(page, selector, timeout = 5000) {
  try {
    const el = await page.waitForSelector(selector, { timeout });
    if (el) {
      await el.click();
      return true;
    }
  } catch (e) {
    console.log(`点击失败: ${selector} - ${e.message}`);
  }
  return false;
}

(async () => {
  console.log('=== 经验萃取AI系统 E2E 全流程测试 ===');
  console.log(`截图目录: ${SCREENSHOT_DIR}`);

  const browser = await chromium.launch({ headless: false, slowMo: 100 });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  try {
    // ===== Step 1: 创建访谈 =====
    console.log('\n--- Step 1: 创建访谈 ---');
    await page.goto(`${BASE_URL}/interviews/new`);
    await page.waitForTimeout(2000);
    await screenshot(page, '01_create_page');

    // 填写表单
    const titleInput = await page.$('input[name="title"], input[placeholder*="主题"], input#title');
    if (titleInput) {
      await titleInput.fill('大客户销售的信任建立技巧——以金融行业为例');
    } else {
      recordBug('blocking', '创建访谈', '未找到主题输入框');
      // 尝试更通用的选择器
      const inputs = await page.$$('input');
      if (inputs.length > 0) {
        await inputs[0].fill('大客户销售的信任建立技巧——以金融行业为例');
      }
    }

    const contextInput = await page.$('textarea[name="context"], textarea[placeholder*="背景"], textarea#context');
    if (contextInput) {
      await contextInput.fill('某省级城商行核心业务系统升级项目，历时10个月最终签约。');
    }

    const expertInput = await page.$('input[name="expert_role"], input[placeholder*="专家"], input#expert_role');
    if (expertInput) {
      await expertInput.fill('资深销售经理');
    }

    await screenshot(page, '02_form_filled');

    // 点击创建按钮
    const createBtn = await page.$('button:has-text("创建"), button[type="submit"]');
    if (createBtn) {
      await createBtn.click();
    } else {
      recordBug('blocking', '创建访谈', '未找到创建按钮');
    }

    // 等待页面跳转（蓝图页或加载中）
    await page.waitForTimeout(3000);
    await screenshot(page, '03_after_create_click');

    // 获取当前URL
    let currentUrl = page.url();
    console.log(`当前URL: ${currentUrl}`);

    // 检查是否在加载中
    if (currentUrl.includes('/new')) {
      // 可能还在加载，等待跳转
      await page.waitForTimeout(5000);
      currentUrl = page.url();
      console.log(`等待后URL: ${currentUrl}`);
    }

    // ===== Step 2: 蓝图页 =====
    console.log('\n--- Step 2: 蓝图页 ---');
    await screenshot(page, '04_blueprint_page');

    // 等待蓝图内容加载
    const hasBlueprint = await waitForText(page, '访谈蓝图', 30000);
    if (!hasBlueprint) {
      recordBug('blocking', '蓝图页', '页面未显示"访谈蓝图"文本');
    }

    // 检查六步流程是否显示
    const hasSteps = await waitForText(page, '复盘事件', 10000);
    if (!hasSteps) {
      recordBug('non-blocking', '蓝图页', '未找到"复盘事件"阶段文本');
    }

    await screenshot(page, '05_blueprint_loaded');

    // 点击确认蓝图按钮
    const confirmBtn = await page.$('button:has-text("确认"), button:has-text("开始访谈")');
    if (confirmBtn) {
      await confirmBtn.click();
    } else {
      recordBug('blocking', '蓝图页', '未找到确认/开始访谈按钮');
    }

    await page.waitForTimeout(2000);
    await screenshot(page, '06_after_blueprint_confirm');

    currentUrl = page.url();
    console.log(`确认蓝图后URL: ${currentUrl}`);

    // 如果弹出录音设置，关闭或跳过
    if (await waitForText(page, '录音', 3000)) {
      const cancelBtn = await page.$('button:has-text("取消"), button:has-text("跳过"), button:has-text("直接开始")');
      if (cancelBtn) {
        await cancelBtn.click();
        await page.waitForTimeout(1000);
      }
      await screenshot(page, '07_recording_dialog');
    }

    // ===== Step 3: 访谈页 =====
    console.log('\n--- Step 3: 访谈页 ---');
    await page.waitForTimeout(2000);
    currentUrl = page.url();
    console.log(`访谈页URL: ${currentUrl}`);

    if (!currentUrl.includes('/chat')) {
      // 可能还没跳转，等待
      await page.waitForTimeout(5000);
      currentUrl = page.url();
    }

    await screenshot(page, '08_chat_page');

    // 检查是否有AI开场白
    const hasWelcome = await waitForText(page, '欢迎', 10000) || await waitForText(page, '你好', 10000);
    if (!hasWelcome) {
      recordBug('non-blocking', '访谈页', '未检测到AI开场白（欢迎/你好）');
    }

    // 模拟多轮回答
    const maxRounds = 15;
    for (let round = 0; round < maxRounds && round < ANSWERS.length; round++) {
      console.log(`\n--- 第 ${round + 1} 轮回答 ---`);

      // 等待AI发送问题（检查输入框是否可用或是否有新消息）
      await page.waitForTimeout(3000);

      // 查找输入框
      const inputSelector = 'textarea[placeholder*="回答"], textarea[placeholder*="输入"], input[type="text"], div[contenteditable="true"]';
      const inputBox = await page.$(inputSelector);

      if (!inputBox) {
        recordBug('blocking', `第${round + 1}轮`, '未找到输入框');
        await screenshot(page, `09_round_${round + 1}_no_input`);
        break;
      }

      // 输入回答
      const answer = ANSWERS[round];
      await inputBox.fill(answer);
      await page.waitForTimeout(500);
      await screenshot(page, `09_round_${round + 1}_input_filled`);

      // 查找并点击下一轮按钮
      const nextBtnSelector = 'button:has-text("下一轮"), button:has-text("发送"), button:has-text("提交")';
      const nextBtn = await page.$(nextBtnSelector);

      if (nextBtn) {
        await nextBtn.click();
        console.log(`  已点击下一轮`);
      } else {
        recordBug('blocking', `第${round + 1}轮`, '未找到下一轮/发送按钮');
        await screenshot(page, `09_round_${round + 1}_no_button`);
        break;
      }

      // 等待系统处理（清洗+LLM生成）
      console.log(`  等待系统处理...`);
      await page.waitForTimeout(8000);

      // 检查是否有错误提示
      const pageText = await page.evaluate(() => document.body.innerText);
      if (pageText.includes('500') || pageText.includes('错误') || pageText.includes('Error')) {
        recordBug('blocking', `第${round + 1}轮`, '页面出现错误提示', pageText.slice(0, 500));
        await screenshot(page, `09_round_${round + 1}_error`);
        break;
      }

      await screenshot(page, `09_round_${round + 1}_completed`);

      // 检查是否已经完成所有阶段
      if (pageText.includes('访谈完成') || pageText.includes('结束') || pageText.includes('报告')) {
        console.log(`  检测到访谈完成信号，结束循环`);
        break;
      }

      // 检查状态栏是否推进
      const stateText = await page.$eval('.state-indicator, .current-state, [class*="state"], [class*="stage"]', el => el.innerText).catch(() => '');
      console.log(`  当前状态: ${stateText}`);
    }

    // ===== Step 4: 结束访谈并查看报告 =====
    console.log('\n--- Step 4: 结束访谈与报告 ---');

    // 尝试点击结束访谈按钮
    const endBtn = await page.$('button:has-text("结束访谈"), button:has-text("完成")');
    if (endBtn) {
      await endBtn.click();
      console.log('  已点击结束访谈');
      await page.waitForTimeout(5000);
    } else {
      console.log('  未找到结束访谈按钮，尝试直接访问报告页');
    }

    await screenshot(page, '10_after_interview_end');

    // 尝试访问报告页
    const interviewIdMatch = currentUrl.match(/\/interviews\/(\d+)/);
    const interviewId = interviewIdMatch ? interviewIdMatch[1] : null;

    if (interviewId) {
      console.log(`  访谈ID: ${interviewId}`);

      // 访问报告页
      await page.goto(`${BASE_URL}/interviews/${interviewId}/report`);
      await page.waitForTimeout(3000);
      await screenshot(page, '11_report_page');

      const reportText = await page.evaluate(() => document.body.innerText);
      if (reportText.includes('报告') || reportText.includes('分析') || reportText.includes('经验')) {
        console.log('  报告页有内容');
      } else {
        recordBug('non-blocking', '报告页', '报告页内容为空或缺少关键文本');
      }

      // 测试三档深度切换
      const depthTabs = await page.$$('button:has-text("简要"), button:has-text("标准"), button:has-text("深度")');
      if (depthTabs.length >= 3) {
        for (const tab of depthTabs) {
          await tab.click();
          await page.waitForTimeout(1500);
        }
        await screenshot(page, '12_report_depth_switch');
      } else {
        recordBug('non-blocking', '报告页', '未找到三档深度切换按钮');
      }

      // 访问素材页
      await page.goto(`${BASE_URL}/interviews/${interviewId}/output`);
      await page.waitForTimeout(3000);
      await screenshot(page, '13_output_page');

      const outputText = await page.evaluate(() => document.body.innerText);
      if (outputText.includes('话术卡') || outputText.includes('检查表') || outputText.includes('流程图')) {
        console.log('  素材页有内容');
      } else {
        recordBug('non-blocking', '素材页', '素材页内容为空或缺少关键文本');
      }
    } else {
      recordBug('blocking', '报告页', '无法从URL提取访谈ID');
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

  // 写入报告文件
  const reportPath = path.join(__dirname, 'e2e_test_report.md');
  const reportContent = `# 经验萃取AI系统 - E2E全流程测试报告

**测试时间**: ${new Date().toLocaleString('zh-CN')}
**前端地址**: ${BASE_URL}
**后端地址**: ${API_URL}

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

  // 如果有阻塞BUG，输出摘要
  const blockingBugs = bugs.filter(b => b.severity === 'blocking');
  if (blockingBugs.length > 0) {
    console.log('\n⚠️ 发现阻塞BUG，需要修复:');
    blockingBugs.forEach(b => console.log(`  - [${b.step}] ${b.description}`));
  }
})();
