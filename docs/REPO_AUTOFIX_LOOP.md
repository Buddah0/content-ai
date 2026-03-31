# Repository Autofix Loop

This loop is designed to validate, debug, fix, and rerun validation gates until the repository is confirmed healthy or a defined stop condition is met.

## How to Run It

If you are a human, you can either drive this loop manually by running the `Makefile` validation targets, or you can delegate to an Antigravity agent by specifying the `repo-validation-loop` skill.

For agents: Execute the skill located in `.agents/skills/repo-validation-loop/SKILL.md`.

## The Loop Strategy

1. **Assess Baseline**: Run the full validation suite (`make validate-all`) to gather all failures.
2. **Classify**: Group failures into categories (static checks, unit tests, build, service, smoke gate).
3. **Fix Smallest First**: Address static errors, then type errors, then unit tests, then the smoke test.
4. **Scope Reruns**: If only Python linting failed, rerun only `make validate-backend`. If tests failed, rerun `pytest`. 
5. **Full Verification**: Once localized reruns pass, execute the full `make validate-all`, ending with `make smoke-test` to guarantee no regressions.

## Progress and Stop Conditions

- **Progress** is defined as resolving at least one failure without introducing new ones in unrelated areas, or uncovering a clear actionable root cause.
- **Stop Conditions**: The loop MUST halt and escalate to a human if:
  - 10 iterations fail to achieve a complete pass.
  - The same fix strategy is repeated and fails >2 times (infinite thrashing).
  - External dependencies or services are missing and cannot be stubbed locally (e.g. `ffmpeg` binary missing).
  - An architectural decision is needed to proceed.
