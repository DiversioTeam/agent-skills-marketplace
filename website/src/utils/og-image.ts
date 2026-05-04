import { existsSync } from "node:fs";
import path from "node:path";

// OG image helper.
//
// Why this file exists:
// - many routes now have page-specific social preview images
// - page files should ask for an image by intent, not repeat file existence
//   checks over and over
// - if a generated image is missing, we want one predictable fallback path
//
// Mental model:
//   page route           -> asks for the matching generated asset
//   generated asset      -> lives under website/public/og/
//   fallback             -> generic image when no route-specific asset exists
//
// Example:
//   /pi/dev-workflow     -> /og/pi-dev-workflow.png
//   /skills/frontend     -> /og/skill-frontend.png
//   /docs/dev-workflow   -> /og/docs-dev-workflow.png
//
// Astro page builds run with `website/` as the working directory in both local
// development and CI. Resolve from `process.cwd()` so the helper keeps working
// even if the compiled module location changes during Astro's build step.
const publicRoot = path.resolve(process.cwd(), "public");

export function getGeneratedOgImage(assetPath: string, fallback = "/og-default.png"): string {
  const normalized = assetPath.startsWith("/") ? assetPath.slice(1) : assetPath;
  return existsSync(path.join(publicRoot, normalized)) ? assetPath : fallback;
}
