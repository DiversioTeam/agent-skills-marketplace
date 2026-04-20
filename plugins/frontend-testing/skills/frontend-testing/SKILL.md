---
name: frontend-testing
description: "Testing guidance for React/TypeScript frontends. Supports unit (Vitest), component (RTL), and E2E (Playwright) testing with coverage analysis and CI failure debugging."
---

# Frontend Testing Skill

Comprehensive testing guide for React/TypeScript frontend applications.

---

## Quick Command Reference

```bash
# Unit & Component Tests (Vitest)
yarn test                  # Run all Vitest tests
yarn test:ui               # Vitest with interactive UI
yarn test:coverage         # Coverage report (text + HTML)
yarn test:unit             # Unit tests only
yarn test:components       # Component tests only
yarn test:integration      # Integration tests only
yarn test:watch            # Watch mode
yarn test:performance      # Performance tests

# E2E Tests (Playwright)
yarn test:e2e              # All E2E tests
yarn test:e2e:critical     # Critical path only (@critical tag)
yarn test:e2e:smoke        # Smoke tests (@smoke tag)
yarn test:e2e:headed       # With visible browser
yarn test:e2e:debug        # Debug mode (step through)
yarn test:e2e:ui           # Playwright interactive UI
yarn test:e2e:report       # View last HTML report

# Full Check (CI equivalent)
yarn check                 # type-check + lint + test
```

---

## Argument Routing

Based on the argument passed:

| Argument    | Action                            |
| ----------- | --------------------------------- |
| (none)      | Show this overview                |
| `unit`      | Guide for writing unit tests      |
| `component` | Guide for writing component tests |
| `e2e`       | Guide for writing E2E tests       |
| `coverage`  | Run coverage and analyze gaps     |
| `run`       | Run the appropriate test suite    |

---

## Unit Tests (Vitest)

### When to Write Unit Tests

- Utility functions (`src/utils/`)
- Custom hooks (`src/hooks/`)
- Redux slices and selectors (`src/store/slices/`)
- Pure logic and data transformations
- Security and monitoring utilities (HIGH priority - 90%+ coverage required)

### File Naming & Location

```
src/utils/formatters.ts          -> src/utils/formatters.test.ts
src/hooks/useAuth.ts             -> src/hooks/useAuth.test.ts
src/store/slices/authSlice.ts    -> src/store/slices/authSlice.test.ts
```

### Test Structure

```typescript
import { describe, it, expect, vi } from 'vitest'

import { functionToTest } from './module'

describe('functionToTest', () => {
    it('should handle the happy path', () => {
        const result = functionToTest(input)
        expect(result).toBe(expected)
    })

    it('should handle edge case', () => {
        expect(() => functionToTest(null)).toThrow()
    })
})
```

### Key Patterns

- Use `vi.mock()` for module mocking
- Use `vi.fn()` for function spies
- Use `vi.useFakeTimers()` for time-dependent tests
- Test file must be adjacent to the source file
- Do NOT mock what you're testing

---

## Component Tests (React Testing Library)

### When to Write Component Tests

- Shared components (`src/components/common/`)
- Complex interactive components
- Components with conditional rendering logic
- Form components with validation

### File Naming & Location

```
src/components/common/EmployeeCard/index.tsx
-> src/components/common/EmployeeCard/EmployeeCard.test.tsx
```

### Test Structure

```typescript
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import { EmployeeCard } from './index'

describe('EmployeeCard', () => {
    it('renders employee name', () => {
        render(<EmployeeCard name="John Doe" role="engineer" />)
        expect(screen.getByText('John Doe')).toBeInTheDocument()
    })

    it('handles click event', async () => {
        const onClick = vi.fn()
        render(<EmployeeCard name="John" onClick={onClick} />)

        await fireEvent.click(screen.getByRole('button'))
        expect(onClick).toHaveBeenCalledOnce()
    })
})
```

### Key Patterns

- Query by accessibility role first (`getByRole`, `getByLabelText`)
- Fall back to `getByText`, then `getByTestId`
- Use `userEvent` over `fireEvent` for realistic interactions
- Wrap state updates in `act()` or use `waitFor()`
- Mock API calls with MSW (see integration tests)

---

## E2E Tests (Playwright)

### When to Write E2E Tests

- Critical user flows (login, upload, field mapping)
- Multi-page journeys
- Role-based access control verification
- Feature flows spanning multiple components

### File Naming & Location

```
tests/e2e/auth/login.spec.ts
tests/e2e/hr/hris-upload.spec.ts
tests/e2e/manager/team-overview.spec.ts
tests/e2e/employee/dashboard.spec.ts
tests/e2e/shared/navigation.spec.ts
```

### Test Structure

```typescript
import { test, expect } from '@playwright/test'

test.describe('Login Flow', () => {
    test('@critical should login with valid credentials', async ({ page }) => {
        await page.goto('/auth/login')
        await page.getByLabel('Email').fill('test@example.com')
        await page.getByRole('button', { name: 'Submit' }).click()

        await expect(page).toHaveURL(/dashboard/)
    })
})
```

### Test Tags

```
@critical  - Must pass for any PR (runs in CI smoke tests)
@smoke     - Quick sanity checks
@visual    - Visual regression tests
@regression - Full coverage (runs in full E2E suite)
```

### Key Patterns

- Use Page Object Model for maintainability
- Use auto-waiting (don't add manual waits)
- Use `data-testid` for stable selectors
- Store auth state in `.auth/` for reuse
- Use `test.describe` to group related tests

### CI Failure Debugging

See `references/e2e-debugging.md` for the full debugging workflow including:
- Two-pass approach (diagnose first, fix second)
- Failure categorization (selector, navigation, auth, flaky, config)
- Artifact-based debugging with traces and screenshots
- Local sandbox testing setup

---

## Integration Tests (MSW)

For testing feature modules with mocked API responses:

```typescript
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

const server = setupServer(
    http.get('/api/v1/users/me', () => {
        return HttpResponse.json({ uuid: '123', role: { role: 'hr_admin' } })
    }),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

File naming: `{module}.integration.test.ts`

---

## Coverage Thresholds

### Current Configuration (vitest.config.ts)

```
Global baseline:              5% (statements, branches, functions, lines)
src/utils/security.ts:        90% (statements, branches, functions, lines)
src/utils/monitoring.ts:      80% (statements, branches, functions, lines)
```

### Exclusions (Not Counted in Coverage)

```
node_modules/
src/test/
**/*.d.ts
**/*.config.*
**/*.types.ts
**/mockData.ts
**/*.styles.ts
```

### Target

30%+ overall by end of testing phases.

---

## Test Setup

The test setup file is at `src/test/setup.ts`. It configures:

- jsdom environment
- CSS support
- Global test utilities

Vitest config: `vitest.config.ts`
Playwright config: `playwright.config.ts`
