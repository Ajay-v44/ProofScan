import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.PROOFSCAN_WEB_URL ?? "http://localhost:3000",
    channel: process.env.PROOFSCAN_BROWSER_CHANNEL,
    trace: "retain-on-failure",
  },
});
