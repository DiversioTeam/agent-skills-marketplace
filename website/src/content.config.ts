import { glob } from "astro/loaders";
import { defineCollection, z } from "astro:content";

// Blog content collection.
//
// Why this file exists:
// - the engineering hub now needs a real editorial surface, not just tool docs
// - original posts and curated reposts need one explicit schema
// - reposts need guardrails so we do not lose attribution or canonical URLs
//
// First principles:
// - keep v1 simple: local markdown in git, reviewed like code
// - make the important publishing rules machine-checkable
// - fail early when a repost is missing source metadata
//
// Mental model for the two post types:
//
//   original post
//     written for this site, canonical URL can stay here
//     example: announcing a new feature or launch
//
//   curated repost
//     originally published elsewhere, cross-posted here with attribution
//     the canonical URL must point to the original
//     the sourceUrl tells readers where the full post lives
//     example: reposting an engineer's personal blog post about Diversio
//
// How to add a repost:
//
//   1. Create a markdown file under src/content/blog/
//   2. Use this frontmatter shape:
//
//      ---
//      title: "The Original Title"
//      slug: original-slug-from-source
//      summary: One-sentence description
//      publishDate: 2025-08-07
//      author:
//        name: Original Author
//        url: https://their-site.com
//      sourceType: repost
//      sourceSiteName: their-site.com
//      sourceUrl: https://their-site.com/original-post/
//      canonicalUrl: https://their-site.com/original-post/
//      ---
//
//   3. The body should be a short intro + link to original.
//      The full article stays on the source site.
//
//   4. Regenerate OG images and rebuild:
//
//      python3 website/scripts/generate-og-images.py
//      cd website && npm run build
//
// Key rules for reposts:
//   - sourceUrl and canonicalUrl are both required (enforced by superRefine)
//   - sourceSiteName is displayed on the blog index and detail pages
//   - canonicalUrl is what search engines see as the authoritative URL
//   - the slug should match the original article's slug for consistency
const blog = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/blog" }),
  schema: z
    .object({
      title: z.string(),
      slug: z.string().optional(),
      summary: z.string(),
      publishDate: z.coerce.date(),
      updatedDate: z.coerce.date().optional(),
      author: z.object({
        name: z.string(),
        url: z.string().url().optional(),
      }),
      tags: z.array(z.string()).default([]),
      sourceType: z.enum(["original", "repost"]),
      sourceSiteName: z.string().optional(),
      sourceUrl: z.string().url().optional(),
      canonicalUrl: z.string().url().optional(),
      heroImage: z.string().optional(),
      socialImage: z.string().optional(),
      socialTitle: z.string().optional(),
      socialDescription: z.string().optional(),
      featured: z.boolean().default(false),
      draft: z.boolean().default(false),
    })
    .superRefine((data, ctx) => {
      if (data.sourceType === "repost" && !data.sourceUrl) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Reposts must include sourceUrl.",
          path: ["sourceUrl"],
        });
      }

      if (data.sourceType === "repost" && !data.canonicalUrl) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Reposts must include canonicalUrl.",
          path: ["canonicalUrl"],
        });
      }
    }),
});

export const collections = { blog };
