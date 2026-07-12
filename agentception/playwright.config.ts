import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 300_000, // 5 minutes per test (workflows are slow)
  expect: { timeout: 60_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['html', { open: 'never' }], ['list']],
  use: {
    baseURL: 'http://localhost:8080',
    video: 'on',              // Always record video
    screenshot: 'on',         // Take screenshots on each step
    trace: 'on',              // Full trace for debugging
    viewport: { width: 1920, height: 1080 },
    launchOptions: {
      slowMo: 500,            // Slow down for visibility in video
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
  // Don't start servers automatically - we manage them ourselves
});
