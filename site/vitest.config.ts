// Unit tests of the code without Nuxt or Cloudflare: the package's checks, the catalog's query (npm test).
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: { "~~": fileURLToPath(new URL(".", import.meta.url)) } },
  test: { include: ["tests/**/*.test.ts"] },
});
