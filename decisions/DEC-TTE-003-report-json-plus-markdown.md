---
id: DEC-TTE-003
status: accepted
date: 2026-05-25
requirements:
  - R-TTE-004
  - R-TTE-005
owner_role: science.proof_gate_runner
---

# Report JSON Plus Markdown

## Decision

Each run writes machine-readable JSON and a Markdown summary from the same result payload.

## Reason

Automation needs stable counts and per-check results. Humans need a short table that names the failed case, suite, trace, and check.

## Consequence

CI, issue comments, and local review can all use one run artifact without extra conversion work.

