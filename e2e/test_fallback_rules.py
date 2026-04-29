"""
经验萃取AI系统 —— 兜底规则浏览器仿真测试计划

测试目标：验证访谈状态推进的五层兜底机制是否正常工作
测试方式：通过 Playwright (Python) 打开真实浏览器，模拟完整的访谈流程

背景：此前 60 分钟访谈在复盘事件阶段 stuck 14 轮未能推进
修复后预期：3 轮内应自动从"复盘事件"推进到"建构框架"

运行方式:
    cd experience-extraction-ai
    python -m pytest e2e/test_fallback_rules.py -v -s

依赖:
    pip install playwright pytest
    python -m playwright install chromium
"""

import pytest
import time
from playwright.sync_api import Page, expect, sync_playwright

# 前端地址
BASE_URL = "http://localhost:5173"

# 测试数据：模拟专家回答（基于之前 stuck 的真实对话记录）
EXPERT_ANSWERS = [
    # 第1轮：案例背景 + 冲突 + 行动 + 结果概述
    """大概在去年的时候，我遇到一个做产业园区的客户，业务比较复杂，涉及政府审批和资金流。
第一次见面时，我问他们最近有没有在资金流上的困惑或困难，他说有。
我就跟他分析了资金流不畅对项目进度、施工安排和资金周转的影响，还引用了类似项目延误几个月的案例。
客户虽然一开始回应比较模糊，但后续问了具体案例和解决方案，表现出兴趣。
我于是主动建议了项目调研，最终客户同意试点合作，建立了信任关系。""",

    # 第2轮：补充具体动作细节
    """当时我是这样切入的：
我先问"你们最近有没有在资金流上有一些困惑或是困难？"他说有。
我就跟他分析说，如果资金流不畅，可能会拖延整个项目进度，影响到施工安排和资金周转。
我还提到，如果资金问题不能及时解决，可能会导致工期延误和资金回笼不及时。
数据方面我引用了一个类似项目的例子，说资金无法及时到位往往延误几个月。
客户后来问了有没有类似案例和解决方案，我就提议安排项目调研深入分析资金流的具体问题。""",

    # 第3轮：补充调研结果和后续反馈
    """调研后我整理了详细报告，包含资金流不畅的具体表现、影响项目的关键环节，以及几种可行的优化方案，例如改善资金周转流程、提高资金调度效率等。
报告中还结合了行业成功案例的对比数据，展示我们的方案如何在实际操作中帮助客户提高效率。
客户对优化方案表示认可，同意在下一步进行试点实施。
虽然这是初步合作，不是大规模推广，但客户已经开始愿意与我们合作了。""",
]


def get_current_state(page: Page) -> str:
    """获取当前阶段文本"""
    state_locator = page.locator("text=/当前阶段：/")
    state_locator.wait_for(state="visible", timeout=5000)
    text = state_locator.text_content() or ""
    return text.replace("当前阶段：", "").strip()


def wait_for_ai_response(page: Page, timeout_ms: int = 120_000):
    """等待 AI 回复完成（发送按钮从 disabled 变为可用）"""
    # 先等 AI 加载指示器出现（表示请求已发出）
    try:
        page.wait_for_selector("text=AI正在深入分析您的回答", timeout=3000)
    except Exception:
        pass  # 可能已经很快完成

    # 等待发送按钮变为可用
    page.wait_for_function(
        """() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                const svg = btn.querySelector('svg');
                if (svg && btn.classList.contains('bg-primary-600')) {
                    return !btn.disabled;
                }
            }
            return false;
        }""",
        timeout=timeout_ms,
    )
    # 额外等待 DOM 更新完成
    page.wait_for_timeout(1500)


def send_message_and_wait(page: Page, content: str):
    """发送消息并等待 AI 回复"""
    textarea = page.get_by_placeholder("请输入您的回答...")
    textarea.fill(content)
    # 点击发送按钮（比按 Enter 更可靠）
    page.locator('textarea[placeholder*="请输入您的回答"] + button').click()
    # 验证消息已发送（textarea 被清空）
    expect(textarea).to_have_value("", timeout=10_000)
    print(f"[测试] 已发送回答，等待 AI 回复...")
    wait_for_ai_response(page, timeout_ms=300_000)
    print(f"[测试] AI 回复完成")


class TestFallbackRules:
    """兜底规则测试类"""

    def test_60min_interview_should_advance_within_3_turns(self, page: Page):
        """
        测试1：60分钟访谈，复盘事件阶段应在3轮内自动推进

        预期行为：
        - MAX_TURNS_PER_STATE = 3
        - 在 3 轮用户回答后，兜底机制应强制推进到"建构框架"阶段
        """
        print("\n" + "=" * 50)
        print("测试1：60分钟访谈兜底规则验证")
        print("=" * 50)

        # Step 1: 访问首页
        print("\n[Step 1] 访问首页")
        page.goto(BASE_URL)
        expect(page.get_by_role("heading", name="经验萃取AI").first).to_be_visible()
        page.screenshot(path="e2e/screenshots/py_01_homepage.png")

        # Step 2: 点击创建新访谈
        print("[Step 2] 点击'开始新的萃取访谈'")
        page.get_by_text("开始新的萃取访谈").click()
        expect(page.get_by_role("heading", name="创建新访谈").first).to_be_visible()
        page.screenshot(path="e2e/screenshots/py_02_create_page.png")

        # Step 3: 填写表单
        print("[Step 3] 填写访谈表单")
        page.get_by_placeholder("例如：新任销售代表的异议处理技巧").fill("金融大客户关系经营")
        page.get_by_placeholder("描述该经验所在的业务场景和背景...").fill(
            "拥有15年大客户销售经验，年均签约额过亿，擅长产业园区客户开发"
        )
        page.get_by_placeholder("例如：资深销售经理").fill("资深销售总监")
        page.locator('input[type="number"]').fill("60")
        page.screenshot(path="e2e/screenshots/py_03_form_filled.png")

        # Step 4: 提交表单，等待蓝图
        print("[Step 4] 提交表单，等待蓝图生成")
        page.locator('button[type="submit"]').click()

        # 等待跳转到蓝图页面（标题出现即视为跳转成功）
        expect(page.get_by_role("heading", name="访谈蓝图").first).to_be_visible(timeout=120_000)

        # 等待蓝图生成完成
        generating = page.locator("text=AI正在生成访谈蓝图")
        try:
            generating.wait_for(state="hidden", timeout=120_000)
            print("[等待] 蓝图生成完毕")
        except Exception:
            print("[信息] 蓝图已加载或无需等待")

        page.screenshot(path="e2e/screenshots/py_04_blueprint.png")

        # Step 5: 确认蓝图并开始访谈
        print("[Step 5] 确认蓝图，进入访谈")
        page.get_by_text("确认蓝图并开始访谈").click()
        expect(page.locator('textarea[placeholder*="请输入您的回答"]')).to_be_visible(timeout=60_000)
        print("[完成] 已进入聊天页面")

        # Step 6: 等待开场问题
        print("[Step 6] 等待开场问题...")
        try:
            page.wait_for_selector("text=AI正在准备开场问题...", timeout=5000)
        except Exception:
            pass

        page.wait_for_function(
            """() => {
                const loadingText = document.querySelector('p.text-gray-600.font-medium');
                return !loadingText || loadingText.textContent !== 'AI正在准备开场问题...';
            }""",
            timeout=120_000,
        )
        page.wait_for_timeout(3000)

        initial_state = get_current_state(page)
        print(f"[初始状态] 当前阶段：{initial_state}")
        page.screenshot(path="e2e/screenshots/py_05_chat_opening.png")

        # 断言：初始状态应为"复盘事件"
        assert "复盘事件" in initial_state, f"初始状态应为'复盘事件'，实际为：{initial_state}"

        # Step 7-9: 逐轮回答，观察状态变化
        current_state = initial_state
        turn_count = 0
        max_turns = 3
        has_advanced = False

        for i in range(max_turns):
            turn_count = i + 1
            print(f"\n{'=' * 50}")
            print(f"第 {turn_count} 轮回答")
            print("=" * 50)

            # 发送回答
            send_message_and_wait(page, EXPERT_ANSWERS[i])
            page.screenshot(path=f"e2e/screenshots/py_06_turn_{turn_count}.png")

            # 检查状态
            new_state = get_current_state(page)
            print(f"[第{turn_count}轮后] 当前阶段：{new_state}")

            # 如果状态已推进
            if new_state != current_state and "复盘事件" not in new_state:
                print(f"[推进] 状态已从'{current_state}'推进到'{new_state}'（第{turn_count}轮后）")
                current_state = new_state
                has_advanced = True

                # 推进到预期阶段则成功
                if any(
                    keyword in new_state
                    for keyword in ["建构框架", "挖掘细节", "识别障碍", "提炼工具", "复述确认"]
                ):
                    print(f"\n[PASS] 测试通过：状态在第{turn_count}轮后成功推进！")
                    break
            else:
                current_state = new_state

        # Step 10: 最终断言
        print("\n" + "=" * 50)
        print("测试断言")
        print("=" * 50)
        print(f"最终状态：{current_state}")
        print(f"实际进行轮数：{turn_count}")

        page.screenshot(path="e2e/screenshots/py_07_final_state.png")

        assert has_advanced, (
            f"预期在{max_turns}轮内从'复盘事件'推进，"
            f"但实际进行了{turn_count}轮后仍为'{current_state}'"
        )
        print("[PASS] 断言通过：状态已成功从'复盘事件'推进")
        print("\n" + "=" * 50)
        print("测试1完成")
        print("=" * 50)

    def test_30min_interview_should_advance_within_2_turns(self, page: Page):
        """
        测试2：30分钟访谈，验证轮数上限计算正确

        预期行为：
        - 30分钟访谈总轮数上限 = 30 / 2.5 = 12 轮
        - 每阶段轮数上限 = 12 / 6 = 2 轮
        - MAX_TURNS_PER_STATE = min(2, 3) = 2
        - 所以在 2 轮后应触发兜底推进
        """
        print("\n" + "=" * 50)
        print("测试2：30分钟访谈轮数上限验证")
        print("=" * 50)

        # 创建 30 分钟访谈
        page.goto(f"{BASE_URL}/interviews/new")
        page.get_by_placeholder("例如：新任销售代表的异议处理技巧").fill("销售异议处理技巧")
        page.get_by_placeholder("描述该经验所在的业务场景和背景...").fill("5年销售经验，擅长处理价格异议")
        page.get_by_placeholder("例如：资深销售经理").fill("销售主管")
        page.locator('input[type="number"]').fill("30")

        page.locator('button[type="submit"]').click()
        expect(page.get_by_role("heading", name="访谈蓝图").first).to_be_visible(timeout=120_000)

        # 等待蓝图
        generating = page.locator("text=AI正在生成访谈蓝图")
        try:
            generating.wait_for(state="hidden", timeout=120_000)
        except Exception:
            pass

        page.get_by_text("确认蓝图并开始访谈").click()
        expect(page.locator('textarea[placeholder*="请输入您的回答"]')).to_be_visible(timeout=60_000)

        # 等待开场问题
        try:
            page.wait_for_selector("text=AI正在准备开场问题...", timeout=5000)
        except Exception:
            pass
        page.wait_for_function(
            """() => {
                const loadingText = document.querySelector('p.text-gray-600.font-medium');
                return !loadingText || loadingText.textContent !== 'AI正在准备开场问题...';
            }""",
            timeout=120_000,
        )
        page.wait_for_timeout(3000)

        initial_state = get_current_state(page)
        assert "复盘事件" in initial_state, f"初始状态应为'复盘事件'，实际为：{initial_state}"
        print(f"[30分钟访谈] 初始状态：{initial_state}")

        # 30分钟访谈的轮数上限：30/2.5=12总轮数，12/6=2轮/阶段，min(2,3)=2
        short_answer = (
            "我在去年遇到一个客户，第一次见面时我主动询问了他们的业务痛点，"
            "通过资金流问题切入，最终成功建立了信任关系。"
        )

        # 第1轮
        send_message_and_wait(page, short_answer)
        state1 = get_current_state(page)
        print(f"[30分钟-第1轮后] 状态：{state1}")

        # 第2轮（此时应触发轮数兜底，因为 30 分钟访谈阶段上限为 2 轮）
        send_message_and_wait(
            page, "后续我安排了项目调研，客户对报告中的优化方案表示认可，同意试点合作。"
        )
        state2 = get_current_state(page)
        print(f"[30分钟-第2轮后] 状态：{state2}")

        has_advanced = "复盘事件" not in state2
        page.screenshot(path="e2e/screenshots/py_08_30min_final.png")

        assert has_advanced, "30分钟访谈应在2轮内从'复盘事件'推进"
        print("[PASS] 30分钟访谈测试通过：2轮后成功推进")
        print("\n" + "=" * 50)
        print("测试2完成")
        print("=" * 50)


# Pytest fixture：提供已配置好的 Page 对象
@pytest.fixture
def page():
    """启动浏览器，返回 Page 对象，测试结束后自动关闭"""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # 打开浏览器，可视化观察
            slow_mo=500,     # 慢动作，便于观察
        )
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        pg = context.new_page()

        # 设置全局超时
        pg.set_default_timeout(120_000)
        pg.set_default_navigation_timeout(60_000)

        yield pg

        # 测试结束后关闭
        context.close()
        browser.close()


if __name__ == "__main__":
    # 直接运行方式（不使用 pytest）
    print("直接运行测试...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        page.set_default_timeout(120_000)
        page.set_default_navigation_timeout(60_000)

        test = TestFallbackRules()
        try:
            test.test_60min_interview_should_advance_within_3_turns(page)
        except Exception as e:
            print(f"[FAIL] 测试1失败: {e}")
            page.screenshot(path="e2e/screenshots/py_error_60min.png")

        try:
            test.test_30min_interview_should_advance_within_2_turns(page)
        except Exception as e:
            print(f"[FAIL] 测试2失败: {e}")
            page.screenshot(path="e2e/screenshots/py_error_30min.png")

        context.close()
        browser.close()
