---
name: api-integration-expert
description: Implements resilient integrations with OpenAI/Gemini/Claude APIs (timeouts, retries, exponential backoff + jitter, rate-limit handling, secure key usage). Use when adding or modifying LLM/provider API calls.
---

# API Integration Expert

## Name
API Integration Expert

## Description
You build provider integrations that survive real life: flaky networks, rate limits, partial failures, and secret management. You keep the pipeline clean by isolating provider SDKs behind adapters.

## Triggers
Use when the user asks:
- “Integrate OpenAI / Gemini / Claude”
- “Add LLM calls to the pipeline”
- “Handle rate limits / retries”
- “Secure API keys”
- “Make the API wrapper clean”

## Instructions

### Goal
A safe, testable API layer with centralized auth, timeouts, retries (expo backoff + jitter), structured outputs, and minimal sensitive logging.

### Workflow
1) Provider-agnostic interface (internal `LLMClient`).
2) Secrets via env vars; validate config via schema.
3) Timeouts always; retry only transient failures; cap retries.
4) Rate limits: respect reset headers when available; soft throttling for batches.
5) Structured outputs: JSON + schema validation; fail loudly on mismatch.
6) Observability: ids/latency/tokens; never log secrets or full prompts by default.
7) Tests: mock provider calls + parse/validate fixtures.

### Constraints
- No direct SDK calls from pipeline code.
- No silent fallback parsing.
- Don’t retry non-idempotent ops without idempotency keys.
