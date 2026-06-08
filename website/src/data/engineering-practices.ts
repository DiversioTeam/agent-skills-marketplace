export interface EngineeringPractice {
  title: string;
  summary: string;
  detail: string;
  relatedHref?: string;
  relatedLabel?: string;
}

export const engineeringPractices: EngineeringPractice[] = [
  {
    title: "Short feedback loops beat late heroics",
    summary:
      "We prefer smaller releases, smaller PRs, and earlier review over giant diffs that only look efficient until the review bill arrives.",
    detail:
      "Break work down early, get feedback while the intent is still fresh, and keep every change small enough that somebody else can reason about it quickly.",
    relatedHref: "/blog/how-we-use-ai-like-engineers",
    relatedLabel: "Related writing",
  },
  {
    title: "Bugs deserve proof",
    summary:
      "If a bug matters, the fix should come with evidence that the failure existed and that the behavior is now correct.",
    detail:
      "Write or update the test that proves the breakage, then land the fix with a reviewer who can see the before-and-after clearly instead of trusting a vague description.",
    relatedHref: "/blog/bugs-deserve-proof",
    relatedLabel: "Related writing",
  },
  {
    title: "Production safety is part of feature work",
    summary:
      "Queries, migrations, large data changes, and risky paths need production-minded thinking long before a change merges.",
    detail:
      "Validate against realistic data, look for performance cliffs, and treat operational safety as part of delivery instead of cleanup after the code is already written.",
    relatedHref: "/blog/how-we-use-ai-like-engineers",
    relatedLabel: "Workflow and review",
  },
  {
    title: "Repeated pain becomes tooling",
    summary:
      "When the same confusion or failure shows up often enough, we try to turn the lesson into a guide, guardrail, wrapper, or reusable tool.",
    detail:
      "Useful knowledge should not stay trapped in one engineer's memory if a small improvement to docs, tooling, or workflow can make it repeatable.",
    relatedHref: "/agentic-tools",
    relatedLabel: "Open tools",
  },
];
