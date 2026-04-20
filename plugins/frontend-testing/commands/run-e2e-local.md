Run E2E tests locally against a Crafting Sandbox.

## Steps

1. Verify CS CLI is ready: `cs info`
2. Find sandbox: `cs sandbox list`
3. Resume if suspended: `cs sandbox resume <name>`
4. Set env vars:

    ```bash
    export E2E_BASE_URL="https://web--<sandbox>.org.sandboxes.run"
    export VITE_API_URL="https://backend--<sandbox>.org.sandboxes.run/optimo/api/v1"
    export E2E_TEST_SECRET="<value>"
    ```

5. Run tests: `yarn test:e2e --project=chromium`
6. View report: `yarn test:e2e:report`

## Quick Commands

```bash
yarn test:e2e --project=chromium --grep '@critical'   # Critical path only
yarn test:e2e --project=chromium --grep '@smoke'      # Smoke tests
yarn test:e2e:headed                                   # Visible browser
yarn test:e2e:debug                                    # Step-through debug
```
