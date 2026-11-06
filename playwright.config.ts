import { defineConfig } from "@playwright/test";

// Its own ports and no reused servers, so these tests can never reach a real model.
const API_PORT = 8010;
const DASHBOARD_PORT = 5183;

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "line",
  timeout: 10_000,
  use: { baseURL: `http://localhost:${DASHBOARD_PORT.toString()}` },
  webServer: [
    {
      command: `uv run python -m e2e.server ${API_PORT.toString()}`,
      url: `http://127.0.0.1:${API_PORT.toString()}/api/health`,
    },
    {
      command: `npx vite dashboard --port ${DASHBOARD_PORT.toString()} --strictPort`,
      url: `http://localhost:${DASHBOARD_PORT.toString()}`,
      env: { API_URL: `http://127.0.0.1:${API_PORT.toString()}` },
    },
  ],
});
