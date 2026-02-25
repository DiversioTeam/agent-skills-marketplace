# GitHub Posting Protocol (monty-code-review)

Use this protocol only when user intent includes posting comments/reviews to a GitHub PR.

## INPUTS_REQUIRED

- `OWNER`
- `REPO`
- `PR`
- `ME` (derive from `gh api user`)

## RULES_MUST

- `MUST_01`: keep one authoritative top-level summary review.
- `MUST_02`: keep one inline anchor per root-cause cluster.
- `MUST_03`: run dedupe audit before and after posting.
- `MUST_04`: keep ascii/diagram content inside fenced `text` blocks.
- `MUST_05`: if line anchor fails (`422`), fallback to file-level inline comment.

## RULES_SHOULD

- `SHOULD_01`: default inline comment cap is 5 unless user asks for more.
- `SHOULD_02`: update existing review in place for formatting fixes; do not add extra summary comments.
- `SHOULD_03`: avoid PR-level issue comments for meta status updates.

## STEP_01_PRE_AUDIT

```bash
OWNER="<owner>"; REPO="<repo>"; PR="<pr_number>"
ME="$(gh api user --jq '.login')"

gh api "repos/$OWNER/$REPO/pulls/$PR/reviews" --paginate \
  --jq ".[] | select(.user.login == \"$ME\") | {id, state, submitted_at}"
gh api "repos/$OWNER/$REPO/pulls/$PR/comments" --paginate \
  --jq ".[] | select(.user.login == \"$ME\") | {id, path, line, created_at}"
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --paginate \
  --jq ".[] | select(.user.login == \"$ME\") | {id, created_at}"
```

## STEP_02_DRAFT

- Prepare one review body with sections:
  1. `What's great`
  2. `Findings` (severity-tagged)
  3. `Open questions` (optional)
  4. `Validation`
- Fence diagrams:

```text
+--------+      +--------+
| issue  | ---> | action |
+--------+      +--------+
```

## STEP_03_POST

- Post review/comments once.
- If partial failure occurs, audit current state and post only missing anchors.

## STEP_04_POST_AUDIT

```bash
gh api "repos/$OWNER/$REPO/pulls/$PR/comments" --paginate --slurp \
  | jq --arg me "$ME" '
      map(if type == "array" then . else [.] end)
      | flatten
      | map(select(.user.login == $me))
      | group_by([.path, (.line // -1), ((.body // "") | split("\n")[0])])
      | map(select(length > 1) | {count: length, path: .[0].path, line: .[0].line, ids: map(.id)})
    '
```

```bash
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --paginate --slurp \
  | jq --arg me "$ME" '
      map(if type == "array" then . else [.] end)
      | flatten
      | map(select(.user.login == $me))
      | group_by(((.body // "") | split("\n")[0]))
      | map(select(length > 1) | {count: length, first_line: ((.[0].body // "") | split("\n")[0]), ids: map(.id)})
    '
```

Pass condition: both duplicate detector results are empty.
