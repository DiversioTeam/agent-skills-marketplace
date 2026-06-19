export interface EngineeringPrinciple {
  label: string;
  description: string;
}

export const engineeringPrinciples: EngineeringPrinciple[] = [
  {
    label: "Real systems over toy demos",
    description:
      "We talk about shipping, review, reliability, cost, and product constraints, not just prompts or playground experiments.",
  },
  {
    label: "AI with guardrails",
    description:
      "Agentic workflows are useful when they live inside explicit review paths, quality gates, and fail-closed automation.",
  },
  {
    label: "Documentation is part of the system",
    description:
      "Runbooks, first-principles notes, and repo-local guides are treated as engineering assets that make systems safer to operate and easier to extend.",
  },
  {
    label: "Make context cheap to recover",
    description:
      "We invest in docs, shared tools, and clearer workflows so engineers can understand the next step without starting from zero each time.",
  },
];
