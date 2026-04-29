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
    video: 'on', // 始终录制视频（E2E 演示用）
    headless: true, // 无头模式，确保视频分辨率严格按 videoSize 录制（720p）
    viewport: { width: 1920, height: 1080 },  // 1920x1080 Full HD
    videoSize: { width: 1920, height: 1080 },
    permissions: ['microphone'], // 自动授予麦克风权限
    launchOptions: {
      args: [
        '--use-fake-device-for-media-stream', // 模拟麦克风设备
        '--use-fake-ui-for-media-stream',     // 自动授予媒体权限
      ],
    },
  },
  timeout: 2_700_000, // 全局超时 45 分钟（8 轮对话 × 500字/分钟 + AI 等待时间 + 报告生成）
  expect: {
    timeout: 180_000, // 断言超时 3 分钟
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 }, // 720p 标准高清
        videoSize: { width: 1280, height: 720 },
      },
    },
  ],
});
