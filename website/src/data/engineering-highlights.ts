// Editorial highlights used by umbrella pages like /systems and /how-we-work.
//
// Keep this file:
// - manual and easy to review
// - concise and high-level
// - focused on patterns, lessons, and reusable ideas
//
// Principles now live in src/data/engineering-principles.ts so page-level editing
// is clearer for staff.

export type EngineeringHighlightLane =
  | "Developer Experience"
  | "Security"
  | "Agentic Tooling"
  | "Documentation"
  | "Product Systems";

export interface EngineeringHighlight {
  slug: string;
  lane: EngineeringHighlightLane;
  title: string;
  summary: string;
  proof: string;
  href?: string;
  hrefLabel?: string;
}

export const engineeringHighlightLaneOrder: EngineeringHighlightLane[] = [
  "Developer Experience",
  "Security",
  "Agentic Tooling",
  "Documentation",
  "Product Systems",
];

export const engineeringHighlights: EngineeringHighlight[] = [
  {
    slug: "multi-repo-workspace",
    lane: "Developer Experience",
    title: "A multi-repo workspace that reduces context switching",
    summary:
      "A unified local workspace, branch-aware worktrees, and shared tooling make it easier to move across product, platform, and tooling work without losing context.",
    proof:
      "The monolith story and the open tooling docs both reflect the same principle: engineering context should be cheap to recover.",
    href: "/blog/the-monolith-that-made-ai-actually-useful",
    hrefLabel: "Related writing",
  },
  {
    slug: "workflow-security-gates",
    lane: "Security",
    title: "Workflow security treated as code, not paperwork",
    summary:
      "GitHub Actions are reviewed as executable infrastructure, with dedicated guardrails that keep workflow changes pinned, auditable, and easier to trust.",
    proof:
      "The workflow-security docs make the operating model easy to inspect, discuss, and reuse.",
  },
  {
    slug: "review-orchestration",
    lane: "Agentic Tooling",
    title: "Review flows that preserve context across passes",
    summary:
      "Agentic review tools, wrapper commands, and review memory help reviewers focus on what changed instead of re-reading the same history from scratch.",
    proof:
      "Marketplace plugins already expose the reusable pieces of this workflow, including review orchestration and structured review memory.",
    href: "/agentic-tools",
    hrefLabel: "Browse the tooling",
  },
  {
    slug: "docs-as-harness",
    lane: "Documentation",
    title: "Docs written for operators, not just for marketing",
    summary:
      "Short routing docs, deeper runbooks, and first-principles explanations turn repeated engineering pain into reusable system knowledge.",
    proof:
      "The tools repo already uses repo-local docs, generated deep-doc pages, and a strong “why this exists” style.",
    href: "/docs",
    hrefLabel: "Read the docs model",
  },
  {
    slug: "api-workflow-from-source-files",
    lane: "Product Systems",
    title: "API workflows anchored in source-controlled request definitions",
    summary:
      "Request collections, docs generation, and reviewable API workflows are kept close to the code so interfaces can evolve with better visibility and less drift.",
    proof:
      "The Bruno API plugin and related writing show the shape of this approach in the open.",
    href: "/blog/from-postman-to-bruno-how-ai-changed-our-api-workflow",
    hrefLabel: "Related writing",
  },
  {
    slug: "measured-ci-improvements",
    lane: "Developer Experience",
    title: "Performance work measured before it is celebrated",
    summary:
      "CI and workflow improvements are treated as engineering changes that should be baselined, measured, and explained rather than justified by instinct alone.",
    proof:
      "Writing and utility docs already reflect a measurement-first posture for CI, delivery, and developer-experience changes.",
    href: "/blog/no-code-by-hand-agentic-platform-acceleration",
    hrefLabel: "Related writing",
  },
];
