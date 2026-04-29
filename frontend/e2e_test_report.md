# 经验萃取AI系统 - E2E全流程测试报告

**测试时间**: 2026/4/28 21:56:10
**前端地址**: http://localhost:5173

## 测试概览

| 指标 | 数值 |
|------|------|
| 总截图数 | 36 |
| BUG总数 | 0 |
| 阻塞BUG | 0 |
| 非阻塞BUG | 0 |

## BUG清单



## 截图文件

- 01_01_create_page.png
- 02_02_form_filled.png
- 03_03_after_create_click.png
- 04_04_blueprint_page.png
- 05_05_blueprint_loaded.png
- 06_06_after_blueprint_confirm.png
- 07_07_after_start_interview.png
- 08_08_chat_page.png
- 09_09_chat_loaded.png
- 10_10_round_1_input_filled.png
- 11_10_round_1_completed.png
- 12_10_round_2_input_filled.png
- 13_10_round_2_completed.png
- 14_10_round_3_input_filled.png
- 15_10_round_3_completed.png
- 16_10_round_4_input_filled.png
- 17_10_round_4_completed.png
- 18_10_round_5_input_filled.png
- 19_10_round_5_completed.png
- 20_10_round_6_input_filled.png
- 21_10_round_6_completed.png
- 22_10_round_7_input_filled.png
- 23_10_round_7_completed.png
- 24_10_round_8_input_filled.png
- 25_10_round_8_completed.png
- 26_10_round_9_input_filled.png
- 27_10_round_9_completed.png
- 28_10_round_10_input_filled.png
- 29_10_round_10_completed.png
- 30_10_round_11_input_filled.png
- 31_10_round_11_completed.png
- 32_11_after_complete.png
- 33_12_report_page.png
- 34_13_report_depth_switch.png
- 35_14_output_page.png
- 36_99_final_state.png

## 修复验证

| BUG | 修复内容 | 验证结果 |
|-----|----------|----------|
| 弹窗遮罩层拦截点击 | `BlueprintPage` 弹窗DOM重构：遮罩层与弹窗内容分离为独立元素，遮罩层添加 `pointer-events-none` | 弹窗"开始访谈"按钮点击成功，无超时 |
| 蓝图生成并发请求 | `handleGenerate` / `loadBlueprint` 增加 `generating` 状态锁 + `useRef` 防止StrictMode重复触发 | 后端日志确认 `POST /blueprint/generate` 仅请求1次 |

---
*报告由浏览器自动化测试脚本生成*
