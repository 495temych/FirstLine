import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // node_modules can be a link out of iCloud, so paths must stay as they're written.
  resolve: { preserveSymlinks: true },
  server: {
    fs: { allow: [".."] },
    proxy: { "/api": process.env.API_URL ?? "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    coverage: {
      include: ["src/**"],
      exclude: ["src/main.tsx", "src/test-data.ts"],
      thresholds: { statements: 80 },
    },
  },
});
