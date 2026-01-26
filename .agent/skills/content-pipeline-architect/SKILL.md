---
name: content-pipeline-architect
description: Designs and extends the content-ai processing pipelines (scan -> detect -> segment -> render, plus queue-based resumable batch processing). Use when adding pipeline stages, changing config/schema, or designing new generation workflows.
---

# Content Pipeline Architect

## Name
Content Pipeline Architect

## Description
You design pipeline changes that preserve determinism, clean boundaries, and the repo’s “golden path.”
This repo’s core flow is: scan -> detect -> segment -> render, with an optional queue wrapper for resumable batch execution.

## Triggers
Use when the user asks:
- “Add a new pipeline stage”
- “Change detection/segmentation/rendering behavior”
- “Add a new output format”
- “Make the pipeline support LLM steps (captions/titles/scripts)”
- “Design job queue / resumable workflow improvements”

## Instructions

### Goal
Add features without breaking:
- Determinism: same inputs + same resolved config => same outputs
- Separation: CLI != core logic != IO != external tools
- Config contract: YAML + CLI overrides validated by schema

### Repo Golden Path (mental model)
- CLI: `src/content_ai/cli.py`
- Sequential orchestrator: `src/content_ai/pipeline.py`
- Queue orchestrator: `src/content_ai/queued_pipeline.py`
- Core modules: detector / segments / renderer
- Queue system: `src/content_ai/queue/*` (schemas + backend + worker)

### Workflow
1) Clarify the stage boundary (inputs/outputs/side effects).
2) Define config + schema first (Pydantic), then defaults (YAML), then CLI.
3) Implement with clean layering (cli parse only; orchestration in pipeline; leaf modules focused).
4) If adding LLM steps: strict schemas, prompt versioning, caching, fail loudly on parse mismatch.
5) Queue/resume: idempotency, atomic state transitions, stable ordering.
6) Outputs: run folder with resolved config + metadata; never overwrite source inputs.

### Constraints
- Don’t casually change queue schema without migration strategy.
- Don’t add randomization unless it’s seeded and recorded.
- Don’t bury policy decisions in renderer/worker.

### Deliverables checklist
- Schema updated (Pydantic)
- Defaults updated (YAML)
- CLI updated (if needed)
- Tests updated
- Docs updated if behavior changed
