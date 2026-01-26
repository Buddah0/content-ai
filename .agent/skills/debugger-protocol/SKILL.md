---
name: debugger-protocol
description: Standardized debugging protocol: Analyze error log -> Reproduce -> Isolate -> Fix -> Verify -> Prevent regression. Use when a bug appears or tests fail.
---

# Debugger Protocol

## Name
Debugger Protocol

## Description
This is a strict troubleshooting playbook. No vibes-based coding. No random “maybe this fixes it” edits.

## Triggers
Use when the user says:
- “This crashed / error / exception”
- “Tests failing”
- “It doesn’t work”
- “Bug in X”
- “Help debug this stack trace”

## Instructions

### Goal
Resolve the bug with high confidence, add verification, and prevent recurrence.

### Workflow (do not reorder)
1) **Analyze Error Log**
   - Extract the exact error message and the failing boundary (file/function).
   - Identify: input, operation, expected vs actual.

2) **Reproduce Issue**
   - Write minimal repro steps (command, inputs, environment).
   - If you can’t reproduce, explain what evidence is missing and propose the smallest experiment.

3) **Isolate Cause**
   - Narrow down to a single root cause hypothesis.
   - Use bisection logic: comment out, add logging, simplify input.
   - Confirm the hypothesis with evidence (not guesses).

4) **Fix**
   - Implement the smallest fix that addresses the root cause.
   - Avoid side-effect refactors while debugging.

5) **Verify**
   - Re-run the failing test or command.
   - Add/adjust tests to cover the bug (regression test).
   - Run lint/format if applicable.

6) **Prevent**
   - Add guardrails: validation, clearer errors, timeouts, better defaults.
   - If relevant, document the gotcha (README/docs) briefly.

### Output format
- **Symptom**
- **Repro steps**
- **Root cause**
- **Fix (summary)**
- **Patch (snippet/diff)**
- **Verification results**
- **Regression test added**
- **Prevention note**

### Constraints
- Never “fix” by suppressing errors unless the user explicitly wants that.
- Never delete tests to make CI pass.
- Prefer deterministic fixes over timing-dependent hacks.
