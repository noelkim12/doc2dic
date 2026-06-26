/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  root: "../",
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./web/tests/setup.ts"],
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./web/src", import.meta.url)),
    },
  },
});
