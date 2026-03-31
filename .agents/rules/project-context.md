---
description: Content-AI repository context and technology stack
---

# Project Context

This is the Content-AI pipeline repository.
The primary execution environment is LOCAL. Do not treat Docker or Kubernetes as the primary source of truth for repository health.

## Technologies
- **Backend/CLI/Worker**: Python >=3.11, managed by `poetry`.
- **Frontend**: Next.js 14, managed by `npm` (inside `web/`).
- **Media Processing**: FFmpeg is an absolute dependency for the pipeline.
- **Job/State Tracking**: SQLite (`content_ai.db`).

## Execution Paths
- The primary processing entrypoint is `content-ai scan`.
- The repository relies on `output/` directories for runs.
- `hype_reel.mp4` is the canonical fixture in the root folder for smoke testing.
