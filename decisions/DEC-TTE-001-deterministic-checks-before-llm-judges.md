---
id: DEC-TTE-001
status: accepted
date: 2026-05-25
requirements:
  - R-TTE-001
  - R-TTE-003
owner_role: science.proof_gate_runner
---

# Deterministic Checks Before LLM Judges

## Decision

The MVP uses exact string, citation span, tool allowlist, and refusal-marker checks before any judge model.

## Reason

Failed traces usually expose concrete evidence: a missing span, a disallowed tool, or an answer that should have refused. These can be checked without network calls, provider setup, or random scoring drift.

## Consequence

The first release catches repeatable regressions. Subjective answer quality waits for a later spec.

