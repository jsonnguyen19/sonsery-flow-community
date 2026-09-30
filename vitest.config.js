import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: [
      "runctx-extension/services/__tests__/**/*.test.js",
    ],
  },
});
