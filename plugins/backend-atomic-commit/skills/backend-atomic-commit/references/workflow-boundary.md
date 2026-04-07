# Workflow Boundary

`backend-atomic-commit` does not own branch creation or PR state by itself.

What it should do:

- read repo-local workflow docs from `AGENTS.md` and linked docs
- surface branch or PR convention mismatches as at least `[SHOULD_FIX]`
- let repo-local conventions win over any generic feature-branch assumption

What it should not do:

- invent a branch naming rule when the repo already documents one
- silently ignore obvious branch/PR convention mismatches
- pretend it is the authority for PR draft/non-draft state
