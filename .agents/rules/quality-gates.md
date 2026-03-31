---
description: Canonical validation rules and blocking constraints
---

# Quality Gates

Do not claim the repository is clean or functioning until ALL BLOCKING gates pass.

## Blocking Gates
1. **Frontend Lint**: `cd web && npm run lint` must exit 0.
2. **Backend Lint**: `poetry run ruff check src/ tests/` must exit 0.
3. **Backend Tests**: `poetry run pytest` must exit 0.
4. **Happy-Path CLI Smoke Test**: `make smoke-test` must complete successfully, producing `.mp4` clip files and a valid `run_meta.json` in the targeted output folder.

## Pre-Run Isolation
- All smoke tests MUST clean their target output directory (e.g., `output/smoke_test/`) before running to guarantee fresh results and prevent stale artifacts from causing false passes.
