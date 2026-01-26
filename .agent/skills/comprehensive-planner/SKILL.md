---
name: comprehensive-planner
description: Forces a planning phase before coding: outlines steps, dependencies, edge cases, test plan, and acceptance criteria. Use when asked to build or modify features.
---

# Comprehensive Planner

## Name
Comprehensive Planner

## Description
You don’t code first. You think first. This skill produces a clean, staged implementation plan that reduces rework and surprise bugs.

## Triggers
Use when the user asks:
- “Build/implement/add feature X”
- “Design the system for…”
- “Add a new module / pipeline”
- “Refactor architecture”
- “Make this production-ready” (for non-trivial changes)

## Instructions

### Goal
Produce a step-by-step plan that can be executed with minimal ambiguity.

### Workflow
1) **Restate the objective**
   - One sentence: what success looks like.

2) **Constraints + assumptions**
   - List constraints the user mentioned.
   - If info is missing, make **reasonable defaults** and label them as assumptions (do not stall with lots of questions).

3) **System touchpoints**
   - Identify files/modules likely impacted.
   - Note boundaries (CLI vs core logic vs storage vs integrations).

4) **Implementation steps (sequenced)**
   - Break into small, safe commits.
   - For each step: what you change + why.

5) **Edge cases + failure modes**
   - Inputs, empty states, timeouts, partial failure, concurrency, bad configs.

6) **Dependencies**
   - New libs/tools needed? Include rationale.
   - Note versioning and compatibility risks.

7) **Acceptance criteria**
   - Bullet list of “done means…” checks.

8) **Test plan**
   - Unit tests + integration tests + smoke checks.
   - Include exact commands when known.

9) **Rollout / rollback**
   - Feature flag? config toggle? safe defaults?
   - How to revert safely if it breaks.

### Output format
- **Objective**
- **Assumptions**
- **Touched areas**
- **Plan (steps)**
- **Edge cases**
- **Dependencies**
- **Acceptance criteria**
- **Test plan**
- **Rollback plan**

### Constraints
- Plan must be executable without hidden steps.
- Prefer incremental delivery over giant PRs.
- Default to simplest thing that works unless the user asked for “fancy.”
