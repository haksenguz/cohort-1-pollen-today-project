/// <reference types="vitest" />
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

// Vitest's own config lives here so vite.config.ts stays a pure Vite
// config and tsc does not have to reconcile Vite's UserConfigExport
// with vitest/config's test field. Vitest auto-discovers this file
// from the project root.
export default defineConfig({
  resolve: {
    // Must match compilerOptions.paths in tsconfig.json and
    // tsconfig.app.json, and resolve.alias in vite.config.ts. Without it
    // here the @/ imports in the shadcn components fail to resolve in
    // tests even though the dev server and the build handle them.
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // The default 5s timeout is too tight on a slow machine. This suite
    // drives the chat screen through user-event, which types a message
    // character by character, and that is CPU-bound. On an x64 laptop a
    // typing test finishes in about a second; under x64 emulation on ARM it
    // takes five, which is not a failure but it looks exactly like one. A
    // test that genuinely hangs still fails, just later.
    testTimeout: 30_000,
    hookTimeout: 30_000,
  },
});
