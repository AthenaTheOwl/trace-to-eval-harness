---
id: DEC-TTE-002
status: accepted
date: 2026-05-25
requirements:
  - R-TTE-002
owner_role: science.eval_curator
---

# Failed Trace Becomes Human-Reviewed Eval Case

## Decision

The ingest command writes a draft eval case with `human_review` fields and TODO markers.

## Reason

A failed trace is evidence, but the expected behavior still needs a person to confirm the target text, allowed tools, and refusal intent before it becomes a release gate.

## Consequence

Generated cases are useful immediately for triage and still carry review friction before they block changes.

