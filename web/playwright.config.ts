import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "tests",
  use: {
    baseURL: "http://127.0.0.1:4173/rom-wiki/",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "python ../scripts/serve_frontend.py --port 4173",
    url: "http://127.0.0.1:4173/rom-wiki/",
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
