---
description: Rules for executing iterative fixes cleanly
---

# Fix Loop Policy

When commanded to fix or clean the repository, execute the loop exactly as follows:

1. Never rewrite broad swaths of the codebase or infrastructure blindly. Proceed surgically.
2. Run `make validate-all`.
3. Categorize failures and tackle the lowest-hanging fruits first (e.g. formatting, syntax errors).
4. Run localized checks (e.g., `make validate-backend` or `npm run lint`) to confirm surgical fixes.
5. If the happy-path smoke test `make smoke-test` fails, prioritize debugging the CLI or pipeline logic over UI changes.
6. **Limit Thrashing**: Stop and escalate if you loop >3 times on the exact same error output without changing underlying variables successfully.
7. **Stop Condition**: Halt if missing external secrets, missing the FFmpeg binary, or hitting a max of 10 loops overall.
