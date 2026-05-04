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
// Example mental model:
//   original post -> published here, canonical can default to this site
//   repost        -> published here, but must still point back to the source
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
