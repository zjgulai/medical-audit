import { defineConfig, devices } from "@playwright/test";

const chromiumRuntime =
  process.env.PLAYWRIGHT_USE_SYSTEM_CHROME === "1" ? { channel: "chrome" as const } : {};
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3030";
const webServerCommand = process.env.PLAYWRIGHT_WEB_SERVER_COMMAND ?? "pnpm dev";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000
  },
  use: {
    baseURL,
    trace: "retain-on-failure"
  },
  webServer: {
    command: webServerCommand,
    url: baseURL,
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
    timeout: 120_000
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], ...chromiumRuntime }
    }
  ]
});
