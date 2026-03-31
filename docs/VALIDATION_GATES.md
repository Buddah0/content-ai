# Content-AI Validation Gates

This document defines the canonical source of truth for repository quality and success criteria.

Multiple validators may exist (CI, local scripts, Antigravity agents), but all must derive their logic from this document.

## 1. Local Static Gates (BLOCKING)
Ensure the code is formatted, typed, and linted.
- **Frontend**: `npm run lint` in `web/`
- **Backend/Worker**: `poetry run ruff check src/ tests/`

## 2. Unit-Level Gates (BLOCKING)
Ensure basic correctness without heavy processing.
- **Backend/Worker**: `poetry run pytest`

## 3. Build & Service Readiness (BLOCKING)
Ensure the environment is ready for real execution.
- **Dependencies**: FFmpeg is in PATH (`content-ai check`)
- **Web**: Next.js app builds properly via `npm run build` (if enforced locally).

## 4. Happy-Path CLI Smoke Gate (BLOCKING)
The ultimate proof of health. The primary processing pipeline MUST succeed end-to-end on a known local fixture.

**Success Criteria**:
1. Output directory is cleared prior to execution to prevent stale artifacts passing the gate.
2. An existing `hype_reel.mp4` is passed into the `content-ai scan` processing entry point.
3. At least one local highlight clip (`clip_XXX.mp4` or `montage.mp4`) is written to the fresh output directory.
4. The structured success artifact (`run_meta.json`) is produced, and it contains valid metrics.

## 5. Container & Infra Gates (NON-BLOCKING)
Docker and K8s checks. Docker is present for `api` and `worker` via `docker-compose`, but the local path is the primary execution truth.
- `docker compose config`
