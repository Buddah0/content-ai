---
name: backend-component-generator
description: Generates code in the content-ai repo style (Python, src layout, click CLI, Pydantic schemas, deterministic pure functions, pytest coverage). Use when adding new modules, CLI commands, pipeline stages, or queue features.
---

# Backend Component Generator (content-ai style)

## Name
Backend Component Generator

## Description
You generate Python code matching this repo’s conventions: `src/` layout, CLI via `click`, schema validation via Pydantic, deterministic pipeline stages, and tests via pytest.

## Triggers
Use when the user asks:
- “Add a new module / feature”
- “Add a CLI command/flag”
- “Extend the queue system”
- “Implement new pipeline behavior”
- “Make it consistent with the repo style”

## Instructions

### Goal
Deterministic, typed, test-backed code with clean boundaries.

### Conventions
- Code: `src/content_ai/`
- Tests: `tests/`
- Defaults: `config/default.yaml`
- `cli.py` parses/dispatches only; logic lives elsewhere.
- Pydantic for config + boundary payloads.
- IO/subprocess/network: clear errors, timeouts, no silent failures.
- Queue backend changes require tests + care (ACID-critical).

### Output expectations
Include touched files + rationale + minimal test plan.

### Constraints
No drive-by refactors. No new deps unless justified. Keep diffs tight.
