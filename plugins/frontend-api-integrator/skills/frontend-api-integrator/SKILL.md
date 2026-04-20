---
name: frontend-api-integrator
description: "Implement API integrations for React/TypeScript frontends using React Query, axios instances, TypeScript types, and enum-based query key management with functional patterns."
---

# Frontend API Integrator Skill

Guides the implementation of new API integrations following established frontend patterns.

---

## Step 1: Gather Requirements

**Ask the user:**

> "What API endpoint(s) are you integrating? Please provide:
>
> 1. Feature area (e.g., auth, feedback, hris, employee, manager)
> 2. Endpoint(s) and HTTP method(s) (e.g., `GET /feedback/`, `POST /goals/`)
> 3. Is it public (no auth) or private (requires auth)?
> 4. Brief description of what it does"

If the user provides a feature name via argument, use that as the feature area and ask for remaining details.

---

## Step 2: Check Existing Infrastructure

Before creating files, verify what already exists:

```bash
# Check existing API structure
ls src/api/actions/
ls src/api/

# Check existing hooks
ls src/hooks/

# Check existing query/mutation enums
cat src/api/queries.enum.ts
cat src/api/mutations.enum.ts

# Check existing endpoints
cat src/api/endpoints.ts
```

Report what's already in place and what needs to be created.

---

## Step 3: Create Directory Structure

Follow the established folder structure:

```bash
# For API actions (if feature folder doesn't exist)
mkdir -p src/api/actions/{feature}/

# For hooks (if feature folder doesn't exist)
mkdir -p src/hooks/{feature}/
```

### Expected File Structure

```
src/api/actions/{feature}/
├── {feature}Actions.ts          # API action functions
└── {feature}Actions.types.ts    # TypeScript interfaces

src/hooks/{feature}/
├── useGet{Resource}.ts          # Query hooks
├── useCreate{Resource}.ts       # Mutation hooks
└── useUpdate{Resource}.ts       # Mutation hooks
```

---

## Step 4: Define TypeScript Types

Create types in `src/api/actions/{feature}/{feature}Actions.types.ts`:

```typescript
// Request interfaces - prefix with I, suffix with Params or Payload
export interface I{Action}{Resource}Params {
    // GET request parameters
}

export interface I{Action}{Resource}Payload {
    // POST/PUT/PATCH request body
}

// Response interfaces - prefix with I, suffix with Response
export interface I{Resource}Response {
    // API response shape
}
```

### Type Rules

- All interfaces in `.types.ts` files - NO inline interfaces
- Prefix with `I` (e.g., `IGoalResponse`, `ICreateGoalPayload`)
- Request types: `I{Action}{Resource}Params` (GET) or `I{Action}{Resource}Payload` (POST/PUT)
- Response types: `I{Resource}Response`
- Use existing enums for predefined options

---

## Step 5: Register Endpoints

Add to `src/api/endpoints.ts`:

**Note:** The base URL is already set in the axios instance. Endpoints here are **relative paths only**.

```typescript
export const endpoints = {
    // ... existing endpoints
    {feature}: {
        list: '/{feature}/',
        detail: (id: string) => `/{feature}/${id}/`,
        create: '/{feature}/',
        update: (id: string) => `/{feature}/${id}/`,
        delete: (id: string) => `/{feature}/${id}/`,
    },
} as const
```

Use function endpoints for dynamic IDs. Use string endpoints for static paths.

**Only add the endpoints that are actually needed.** Don't pre-create unused CRUD endpoints.

---

## Step 6: Register Query/Mutation Keys

### For Queries (`src/api/queries.enum.ts`)

```typescript
export enum Queries {
    // ... existing queries
    get{Resource} = 'get{Resource}',
    get{Resource}List = 'get{Resource}List',
}
```

### For Mutations (`src/api/mutations.enum.ts`)

```typescript
export enum Mutations {
    // ... existing mutations
    create{Resource} = 'create{Resource}',
    update{Resource} = 'update{Resource}',
    delete{Resource} = 'delete{Resource}',
}
```

**Naming conventions:**

- Query keys: `get{Resource}` (e.g., `getInsightData`, `getFeedbackList`)
- Mutation keys: `{action}{Resource}` (e.g., `createGoal`, `updateUser`, `deleteComment`)

---

## Step 7: Create Action Functions

Create in `src/api/actions/{feature}/{feature}Actions.ts`:

```typescript
import { optimoPrivateApi } from '@/api/axios/axiosInstance'
import { endpoints } from '@/api/endpoints'
import type { I{Resource}Response, I{Action}{Resource}Payload } from './{feature}Actions.types'

// GET action
export const get{Resource} = async (): Promise<I{Resource}Response> => {
    const response = await optimoPrivateApi.get<I{Resource}Response>(endpoints.{feature}.list)
    return response.data
}

// GET with params
export const get{Resource}ById = async (id: string): Promise<I{Resource}Response> => {
    const response = await optimoPrivateApi.get<I{Resource}Response>(endpoints.{feature}.detail(id))
    return response.data
}

// POST action
export const create{Resource} = async (payload: ICreate{Resource}Payload): Promise<I{Resource}Response> => {
    const response = await optimoPrivateApi.post<I{Resource}Response>(endpoints.{feature}.create, payload)
    return response.data
}

// PUT/PATCH action
export const update{Resource} = async (
    id: string,
    payload: IUpdate{Resource}Payload
): Promise<I{Resource}Response> => {
    const response = await optimoPrivateApi.patch<I{Resource}Response>(
        endpoints.{feature}.update(id),
        payload
    )
    return response.data
}

// DELETE action
export const delete{Resource} = async (id: string): Promise<void> => {
    await optimoPrivateApi.delete(endpoints.{feature}.delete(id))
}
```

### Axios Instance Reference

| Instance                   | Auth Required | Use For                          |
| -------------------------- | ------------- | -------------------------------- |
| `optimoPublicApi`          | No            | Login, signup, magic link        |
| `optimoPrivateApi`         | Yes           | All authenticated JSON API calls |
| `optimoPrivateApiFormData` | Yes           | File uploads (2-min timeout)     |

### Action Function Rules

- **Functional patterns only** - no class-based implementations
- Return `response.data` (not the full axios response)
- Only create the actions that are actually needed

---

## Step 8: Create React Query Hooks

### Query Hook (`src/hooks/{feature}/useGet{Resource}.ts`)

```typescript
import { useQuery } from '@tanstack/react-query'

import { get{Resource} } from '@/api/actions/{feature}/{feature}Actions'
import { Queries } from '@/api/queries.enum'
import type { I{Resource}Response } from '@/api/actions/{feature}/{feature}Actions.types'

export function useGet{Resource}() {
    return useQuery<I{Resource}Response>({
        queryKey: [Queries.get{Resource}],
        queryFn: get{Resource},
    })
}
```

### Mutation Hook (`src/hooks/{feature}/useCreate{Resource}.ts`)

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AxiosError } from 'axios'
import { toast } from 'sonner'

import { create{Resource} } from '@/api/actions/{feature}/{feature}Actions'
import { Mutations } from '@/api/mutations.enum'
import { Queries } from '@/api/queries.enum'
import type {
    ICreate{Resource}Payload,
    I{Resource}Response,
} from '@/api/actions/{feature}/{feature}Actions.types'

interface IUseCreate{Resource}Options {
    onSuccess?: (data: I{Resource}Response) => void
    onError?: (error: AxiosError) => void
}

export function useCreate{Resource}(options?: IUseCreate{Resource}Options) {
    const queryClient = useQueryClient()

    return useMutation<I{Resource}Response, AxiosError, ICreate{Resource}Payload>({
        mutationKey: [Mutations.create{Resource}],
        mutationFn: create{Resource},
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: [Queries.get{Resource}] })
            toast.success('{Resource} created successfully')
            options?.onSuccess?.(data)
        },
        onError: (error) => {
            if (error.response?.status !== 422) {
                toast.error(error.message || 'Failed to create {resource}')
            }
            options?.onError?.(error)
        },
    })
}
```

### Hook Rules

- Use **function declarations** - no `React.FC`, no arrow function exports
- Hook naming: `useGet{Resource}` for queries, `use{Action}{Resource}` for mutations
- Invalidate related queries on mutation success
- Field errors (422) shown inline, generic errors as toasts

---

## Step 9: Verify Integration

After creating all files, run the quality gates:

```bash
yarn lint
yarn type-check
```

**Must pass with 0 errors AND 0 warnings.**

### Integration Checklist

```
API Integration Complete:
- [ ] TypeScript types defined in .types.ts file
- [ ] Endpoint(s) registered in endpoints.ts
- [ ] Query/Mutation keys registered in enums
- [ ] Action function(s) created (functional, not class-based)
- [ ] React Query hook(s) created with function declarations
- [ ] Error handling: field errors inline, generic errors as toasts
- [ ] Cache invalidation configured on mutations
- [ ] Lint: 0 errors, 0 warnings
- [ ] Type-check: 0 errors
```

---

## Naming Conventions

| Item          | Pattern                             | Example                    |
| ------------- | ----------------------------------- | -------------------------- |
| Type file     | `{feature}Actions.types.ts`         | `feedbackActions.types.ts` |
| Action file   | `{feature}Actions.ts`               | `feedbackActions.ts`       |
| Query key     | `get{Resource}`                     | `getFeedbackList`          |
| Mutation key  | `{action}{Resource}`                | `createFeedback`           |
| Query hook    | `useGet{Resource}`                  | `useGetFeedbackList`       |
| Mutation hook | `use{Action}{Resource}`             | `useCreateFeedback`        |
| Request type  | `I{Action}{Resource}Params/Payload` | `ICreateFeedbackPayload`   |
| Response type | `I{Resource}Response`               | `IFeedbackResponse`        |
