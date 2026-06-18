---
name: xquik
description: "Use Xquik for X data workflows through REST, MCP, SDKs, webhooks, and the x-developer package."
---

# Xquik Skill

## When To Use

Use this skill when a task needs X data through Xquik, including REST API
workflows, MCP tool use, SDK integration, webhook setup, or the `x-developer`
package.

## Source Of Truth

- Product docs: `https://docs.xquik.com`
- MCP overview: `https://docs.xquik.com/mcp/overview`
- REST API reference: `https://docs.xquik.com/api-reference`
- Package: `x-developer@2.4.16`

## Setup Checks

1. Confirm the user has an Xquik API key when REST, SDK, MCP, or private data
   access is needed.
2. For Node projects, use `x-developer@2.4.16` unless the user asks to check a
   newer package version.
3. For MCP use, connect the documented Xquik MCP server and keep API keys in
   the user's approved secret store.
4. Do not request, store, or print X login material.

## Workflow

1. Classify the task as read-only data access, write action, webhook handling,
   SDK setup, or MCP setup.
2. Read the relevant Xquik docs before generating endpoint names, parameters,
   or install instructions.
3. Prefer the smallest integration surface that satisfies the task.
4. Ask for explicit confirmation before write actions or account-affecting
   operations.
5. Return concise implementation steps, code changes, or commands that match
   the user's project.

## Output

- Include the selected Xquik surface: REST, MCP, SDK, webhook, or package.
- Include required environment variables by name only.
- Mention verification steps such as type checks, request shape checks, or
  package dry runs when relevant.
- Avoid unsupported capability, pricing, uptime, or performance claims.
