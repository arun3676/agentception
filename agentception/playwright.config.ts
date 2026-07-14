import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const ROOT = path.resolve(__dirname);
const FRONTEND_URL = process.env.E2E_FRONTEND_URL ?? "http://127.0.0.1:18080";
const BACKEND_URL = process.env.E2E_BACKEND_URL ?? "http://127.0.0.1:18000";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  outputDir: "./test-results/playwright",
  timeout: 45_000,
  expect: { timeout: 7_500 },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 2,
  reporter: [["list"]],
  use: {
    baseURL: FRONTEND_URL,
    actionTimeout: 7_500,
    navigationTimeout: 30_000,
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    trace: "retain-on-failure",
    serviceWorkers: "block",
    locale: "en-US",
    timezoneId: "America/Los_Angeles",
    reducedMotion: "reduce",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } },
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
    },
  ],
  webServer: [
    {
      command: "uv run --locked python -m uvicorn server.app:app --host 127.0.0.1 --port 18000",
      cwd: ROOT,
      url: `${BACKEND_URL}/health`,
      timeout: 30_000,
      reuseExistingServer: false,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        APP_ENV: "test",
        FRONTEND_ORIGINS: FRONTEND_URL,
        SUPABASE_URL: "",
        SUPABASE_SERVICE_ROLE_KEY: "",
        DATABASE_URL: "",
        TAVILY_API_KEY: "",
        EXA_API_KEY: "",
        VOYAGE_API_KEY: "",
        DEEPSEEK_API_KEY: "",
        OPENAI_API_KEY: "",
        REDUCTO_API_KEY: "",
      },
    },
    {
      command: "npm --prefix ui run dev -- --host 127.0.0.1 --port 18080 --strictPort",
      cwd: ROOT,
      url: FRONTEND_URL,
      timeout: 30_000,
      reuseExistingServer: false,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        VITE_BACKEND_URL: BACKEND_URL,
      },
    },
  ],
});
