# Redaction Rules

Read when: reviewing a transcript preview, explaining what was removed, or
changing `scripts/redaction.py`.

Two layers. This skill redacts on the developer's machine before upload; Courage
re-checks the published page with its own patterns and the values in its vault.
Keep `SECRET_RULES` in step with Courage's `SECRET_SHAPES`
(`src/workspace-tools.ts` in DiversioTeam/courage).

## Replaced in place

| Kind | Examples |
| --- | --- |
| Secret shapes | GitHub, Slack, AWS, OpenAI/Anthropic, Stripe, 1Password, Google, npm tokens; private keys; Courage tokens |
| Known secrets | Exact values from `.env*` files in the repo and its worktrees, and from environment variables named like `*KEY*`, `*TOKEN*`, `*SECRET*`, `*PASSWORD*` (not `*_ID`, `*_FILE`, paths) |
| Headers and cookies | `Authorization`, `x-api-key`, `Cookie`, `Set-Cookie`, `Bearer`/`Basic` values |
| URLs | OAuth `code`, `state`, tokens and signatures in query strings; `user:password@` credentials; Sentry-style DSN keys |
| JWTs | `eyJ…` three-part tokens |
| Named secrets | `API_TOKEN=…`, `"password": "…"` when the value looks like a credential |
| Personal data | Emails outside diversio.com, optimoteams.com, GitHub noreply and example domains; North American phone numbers |

## Withheld whole

The tool call still shows its input; the output is replaced with a reason.

- **credential file:** reads or writes of `.env*` (not `.example`), `*.pem`,
  `*.key`, SSH keys, `.npmrc`, `.netrc`, `credentials*`, `secrets*`, cookie
  stores, and anything under `.ssh`, `.aws`, `.kube`, `.gnupg`, `.docker`,
  whether a file tool or a shell command (`cat`, `source`, `cp`) touches them.
- **background output:** `TaskOutput`, `BashOutput` and reads of a background
  task's output file inherit the withholding of the call that started the task;
  output from a task of unknown origin is withheld.
- **command prints credentials:** `env`, `printenv`, `op read|inject|run`,
  `security find-*-password`, `gh auth token`, `aws configure export-credentials`,
  `kubectl get secret`, `cat .env`, and similar.
- **prod or staging data access:** `ssh`, `psql`, `mysql`, `redis-cli`,
  `manage.py`, `kubectl`, `curl` and similar aimed at a prod or staging host or
  settings module, and database or Django MCP tools. `--include-output N`
  publishes one turn's output when the developer asks.
- **looks like personal data:** outputs with repeated personal keys
  (`email`, `first_name`, `phone`, …), such as query results and CSVs.

Structured tool inputs (a `Write`'s content, MCP arguments) are redacted value
by value before they are shown as JSON, so escaping cannot hide a known secret.

## Clipped or dropped

Tool outputs keep about 4,000 characters (file reads 2,000), inputs 3,000,
prompts and replies 20,000, with the middle omitted. Model thinking is never
included. Images are dropped. Pages over 20 MB split into linked parts.

## Limits

Names and free-text personal details cannot be detected reliably; that is why
data-shaped outputs and prod or staging access are withheld rather than
scrubbed. The developer's review of the preview is part of the control.
