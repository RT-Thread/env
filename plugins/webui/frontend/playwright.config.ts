import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'line',
  use: {
    browserName: 'chromium',
    launchOptions: process.env.CI ? {} : { executablePath: '/usr/bin/google-chrome' },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
})
