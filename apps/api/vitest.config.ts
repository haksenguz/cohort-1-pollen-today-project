import { defineConfig } from "vitest/config";
import swc from "unplugin-swc";

export default defineConfig({
  plugins: [
    swc.vite({
      jsc: {
        parser: {
          syntax: "typescript",
          decorators: true,
          dynamicImport: true,
        },
        transform: {
          decoratorMetadata: true,
        },
        target: "es2022",
      },
      module: { type: "es6" },
    }),
  ],
  test: {
    include: ["test/**/*.spec.ts"],
    environment: "node",
    globals: true,
    setupFiles: ["test/setup.ts"],
    hookTimeout: 120000,
    testTimeout: 60000,
  },
});
