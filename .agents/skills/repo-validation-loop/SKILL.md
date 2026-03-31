---
name: Repo Validation Loop
description: Autonomous loop to systematically validate, debug, and patch the Content-AI repository until all blocking gates pass.
---

# Repo Validation Loop

You must execute the iterative fix loop for the repository to guarantee health.

## Step 1: Baseline Check
Run the global validation script:
```bash
make validate-all
```
If this succeeds, immediately run the smoke test:
```bash
make smoke-test
```
If both succeed, the repository is healthy. You may exit the loop.

## Step 2: Fix & Rerun
If there are failures:
1. Identify the easiest failure block (e.g., Ruff linting errors).
2. Fix the file(s).
3. Run the scoped validation (e.g., `make validate-backend` or `make validate-frontend`).
4. Repeat until scoped checks pass, then fall back to the global `make validate-all` and `make smoke-test`.

## Step 3: Stop Conditions
- You are not allowed to run infinitely. Max 10 attempts at fixing total.
- You must escalate if the same unit test or smoke test fails >2 times despite your changes.
- Do NOT rewrite existing application logic unless the test clearly indicates a regression caused by a recent, known refactor.

## Step 4: Final Reporting
When finished, strictly report:
1. Whether the entire blocking suite now passes.
2. Which files were changed.
3. If the loop was aborted early, clearly state EXACTLY what is blocking the pipeline.
