---
description: "Set up and verify HOL Guard runtime protection for a supported local AI harness."
argument-hint: "[harness] [--status | --dry-run | --approvals | --receipts]"
---

Use your `hol-guard` Skill to protect or inspect the requested local AI harness.

Treat `$ARGUMENTS` as an optional harness and operation hint. If no harness is supplied, use `hol-guard detect --json` as the source of truth instead of guessing.

For setup, keep the Guard-owned sequence intact: bootstrap, install the detected harness, run a protected dry run, verify with `doctor`, then start the protected harness only when Guard reports a healthy state.

Guardrails:
- Never bypass a Guard deny or approval request.
- Do not claim protection without current `hol-guard` output proving it.
- Preserve native harness authentication, permissions, confirmations, and sandboxing.
- Keep Guard Cloud optional and user-directed.
- Use `plugin-scanner` separately when the request is package, skill, plugin, or MCP verification rather than runtime protection.
