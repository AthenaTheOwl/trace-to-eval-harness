---
id: DEC-TTE-007-run-evidence-packet-as-review-boundary
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-007
date: 2026-05-27
status: approved
reversible: true
decision: |
  Run evidence is a versioned JSON packet that records the inputs,
  tool and MCP surfaces, policy decisions, approvals, artifact diffs,
  gate results, trace refs, and rollback refs around a run. The packet
  is the review boundary between agent action and system truth.
alternatives:
  - label: treat runtime state as the evidence packet
    rejected_because: |
      Runtime state is a resume boundary. It does not necessarily
      include file hashes, policy decisions, gate results, or rollback
      refs from the surrounding control plane.
  - label: keep evidence only in CDCP event logs
    rejected_because: |
      Event logs are append-only history. Reviewers and CI need a
      compact packet that points at the relevant entries and validates
      against a stable schema.
  - label: wait for a vendor-specific trace export
    rejected_because: |
      Vendor trace formats will differ. The local packet should accept
      those refs later without making one runtime authoritative.
rationale: |
  R-TTE-007 and R-TTE-SCHEMA-005 make run evidence portable. Agent
  runtimes act; CDCP records; run evidence decides whether the action
  is ready for evaluation, review, or promotion into another system.
  The first generator reads CDCP event logs because those already exist
  across the portfolio.
evidence:
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
  - kind: schema
    ref: schemas/run-evidence.schema.json
  - kind: code
    ref: trace_to_eval/run_evidence.py
  - kind: test
    ref: tests/test_run_evidence.py
rollback: |
  Remove the run evidence schema, evidence CLI subcommands, generator,
  fixtures, and tests. Existing trace, eval, report, and CDCP event
  adapter behavior remains.
owner: platform
---

## decision

Run evidence is a versioned JSON packet that records the inputs, tool
and MCP surfaces, policy decisions, approvals, artifact diffs, gate
results, trace refs, and rollback refs around a run. The packet is the
review boundary between agent action and system truth.

## alternatives

- Treat runtime state as the evidence packet. Rejected because runtime
  state is a resume boundary and may not include file hashes, policy
  decisions, gate results, or rollback refs.
- Keep evidence only in CDCP event logs. Rejected because event logs are
  append-only history, while reviewers and CI need a compact packet that
  validates against a stable schema.
- Wait for a vendor-specific trace export. Rejected because vendor trace
  formats will differ, and one runtime should not become authoritative.

## rationale

R-TTE-007 and R-TTE-SCHEMA-005 make run evidence portable. Agent
runtimes act; CDCP records; run evidence decides whether the action is
ready for evaluation, review, or promotion into another system. The
first generator reads CDCP event logs because those already exist across
the portfolio.

## evidence

- `specs/0001-trace-to-eval-harness/requirements.md`
- `schemas/run-evidence.schema.json`
- `trace_to_eval/run_evidence.py`
- `tests/test_run_evidence.py`

## rollback

Remove the run evidence schema, evidence CLI subcommands, generator,
fixtures, and tests. Existing trace, eval, report, and CDCP event
adapter behavior remains.
