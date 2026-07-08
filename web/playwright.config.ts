import { defineConfig, devices } from "@playwright/test";

const chromeExecutablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
const desktopChrome = {
  ...devices["Desktop Chrome"],
  ...(chromeExecutablePath
    ? { launchOptions: { executablePath: chromeExecutablePath } }
    : {})
};

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000
  },
  use: {
    baseURL: "http://localhost:3030",
    trace: "retain-on-failure"
  },
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3030",
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
    timeout: 120_000
  },
  projects: [
    {
      name: "chromium",
      use: desktopChrome
    }
  ]
});
