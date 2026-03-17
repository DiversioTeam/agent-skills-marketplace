# Error Handling Reference

Use direct, actionable errors for publish mode. Keep the local HTML path in the
message whenever publish fails after generation.

## Local File Errors

### Missing HTML File

```text
The generated HTML file was not found.

Write the explainer to ~/.agent/diagrams/ first, then retry publish mode.
```

## Token And Config Errors

### Missing Token

```text
NETLIFY_VISUAL_EXPLAINER_TOKEN not found.

Add it to your shell profile:

  export NETLIFY_VISUAL_EXPLAINER_TOKEN="..."

If you already added it there, restart the current tool session or rerun from a
shell session that inherited the export.
```

### Missing Account Slug

```text
NETLIFY_VISUAL_EXPLAINER_ACCOUNT_SLUG not found.

Add it to your shell profile:

  export NETLIFY_VISUAL_EXPLAINER_ACCOUNT_SLUG="your-team-slug"

If you already added it there, restart the current tool session or rerun from a
shell session that inherited the export.
```

### Invalid Token

```text
Netlify API authentication failed.

Check whether NETLIFY_VISUAL_EXPLAINER_TOKEN is valid and still active.
```

## Netlify API Errors

### Site Creation Failed

```text
Could not create a new Netlify preview site.

Check NETLIFY_VISUAL_EXPLAINER_ACCOUNT_SLUG, token permissions, and network
access.
```

### Deploy Creation Failed

```text
Could not upload the explainer to Netlify.

The local HTML still exists. Check token permissions and try again.
```

### Deploy Polling Timed Out

```text
Netlify deploy did not reach ready state before the timeout.

The local HTML still exists. Check Netlify deploy status and retry publish if
needed.
```

### Deploy Failed

```text
Netlify reported a failed deploy.

The local HTML still exists. Check the deploy details in Netlify and retry
after fixing the issue.
```
