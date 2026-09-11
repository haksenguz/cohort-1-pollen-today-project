/// <reference types="vitest" />
import { defineConfig } from "vitest/config";

// Vitest's own config lives here so vite.config.ts stays a pure Vite
// config and tsc does not have to reconcile Vite's UserConfigExport
// with vitest/config's test field. Vitest auto-discovers this file
// from the project root.
export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
