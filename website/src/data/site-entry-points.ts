import { siteConfig } from "../../site.config.mjs";

export interface SiteEntryPoint {
  key: "howWeWork" | "systems" | "tools" | "blog";
  label: string;
  title: string;
  description: string;
  href: string;
  cta: string;
}

export const siteEntryPoints: Record<SiteEntryPoint["key"], SiteEntryPoint> = {
  howWeWork: {
    key: "howWeWork",
    label: "How We Work",
    title: "How We Work",
    description: "Standards, habits, and review culture that shape how Diversio Engineering builds.",
    href: siteConfig.routes.howWeWork,
    cta: "Explore how we work",
  },
  systems: {
    key: "systems",
    label: "Systems",
    title: "Systems",
    description: "Workflows, stack choices, guardrails, and design decisions behind the tools and docs.",
    href: siteConfig.routes.systems,
    cta: "Browse systems",
  },
  tools: {
    key: "tools",
    label: siteConfig.toolsSectionName,
    title: siteConfig.toolsSectionName,
    description: "Registry, deep docs, and runtime-specific guides for the open tools and packages we publish.",
    href: siteConfig.routes.tools,
    cta: "Open tools",
  },
  blog: {
    key: "blog",
    label: "Writing",
    title: "Engineering writing",
    description: "Original posts, curated reposts, and longer-form thinking about the systems and habits behind the work.",
    href: siteConfig.routes.blog,
    cta: "Read the blog",
  },
};
