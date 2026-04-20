Implement a new API integration following frontend patterns.

## Input

The user optionally provides: `$ARGUMENTS` (feature name)

If provided, use as the feature area. Otherwise, ask for endpoint details.

## Steps

1. Gather requirements: feature area, endpoints, HTTP methods, auth requirements
2. Check existing infrastructure (actions, hooks, endpoints, enums)
3. Create directory structure
4. Define TypeScript types in `.types.ts` file
5. Register endpoints in `endpoints.ts`
6. Register query/mutation keys in enums
7. Create action functions (functional, return `response.data`)
8. Create React Query hooks (function declarations)
9. Run lint + type-check (0 errors, 0 warnings)

## Quick Reference

- **Axios instances:** `optimoPublicApi` (no auth), `optimoPrivateApi` (auth), `optimoPrivateApiFormData` (uploads)
- **Query hooks:** `useGet{Resource}` with `useQuery`
- **Mutation hooks:** `use{Action}{Resource}` with `useMutation`
- **Error handling:** 422 inline, others as toasts
- **Cache:** Invalidate related queries on mutation success
