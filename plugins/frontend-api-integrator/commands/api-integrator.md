Implement a frontend API integration using the repo-local digest and detected
contract source.

## Input

The user optionally provides: `$ARGUMENTS` (feature name)

If provided, use as the feature area. Otherwise, ask for endpoint details.

## Steps

1. Load or refresh `docs/frontend-skill-digest/project-digest.md`
2. Identify the affected frontend package and local client pattern
3. Choose the API contract source in this order: generated SDK, OpenAPI /
   Swagger, Bruno/Postman/Insomnia, local backend code, external backend path
4. Ask for a backend working directory or spec path only if the repo does not
   already provide enough contract context
5. Implement using the repo’s real API/client architecture
6. Run digest-selected quality gates

## Quick Reference

- Prefer the repo’s existing client/service pattern over a fixed scaffold.
- Swagger/OpenAPI, Bruno, monolith backend code, or a sibling backend repo can
  all be valid contract sources.
- If backend context is missing, request it explicitly instead of guessing.
