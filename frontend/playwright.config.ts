import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright 配置文件
 * 用于测试经验萃取AI系统的兜底规则
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // 串行执行，避免同时创建多个访谈
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1, // 单 worker，避免并行干扰
  reporter: [['html', { outputFolder: 'playwright-report' }], ['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
    headless: false, // 打开浏览器，可视化观察
    viewport: { width: 1280, height: 720 },
    launchOptions: {
      slowMo: 500, // 慢动作，便于观察
    },
  },
  timeout: 300_000, // 全局超时 5 分钟（LLM 调用较慢）
  expect: {
    timeout: 120_000, // 断言超时 2 分钟
  },
  projects: [
    {
      name: 'chrome',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome', // 使用系统已安装的 Chrome，避免下载 Chromium
      },
    },
  ],
});
