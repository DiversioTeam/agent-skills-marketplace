import { defineConfig } from "astro/config";
import { siteConfig } from "./site.config.mjs";

// https://astro.build/config
export default defineConfig({
  site: siteConfig.siteUrl,
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
