import { defineConfig } from "astro/config";

// https://astro.build/config
export default defineConfig({
  site: "https://agents.diversio.com",
  output: "static",
  build: {
    // Cloudflare-friendly: no inline assets > 4KB
    inlineStylesheets: "auto",
  },
  // Cloudflare-specific: ensure assets use content hashing for immutable caching
  vite: {
    build: {
      assetsInlineLimit: 0,
    },
  },
});
