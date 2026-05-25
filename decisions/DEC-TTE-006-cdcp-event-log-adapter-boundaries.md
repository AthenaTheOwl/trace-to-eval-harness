---
id: DEC-TTE-006-cdcp-event-log-adapter-boundaries
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-006
date: 2026-05-25
status: approved
reversible: true
decision: |
  The CDCP event-log adapter extracts draft eval cases only from
  explicit event payload fields on failed gate, review finding, and
  incident events. It skips malformed JSONL lines, ignores unsupported
  events, and marks every generated case as review-needed before any
  promotion to a release gate.
alternatives:
  - label: infer missing trace facts from event names and notes
    rejected_because: |
      Event notes can be short or human-written. Treating them as
      trace facts would let the adapter invent expected behavior that
      was not present in the payload.
  - label: auto-promote event-derived cases
    rejected_because: |
      A failed gate, review finding, or incident is evidence for a
      draft. A human still needs to decide the expected behavior and
      whether the case belongs in a binding suite.
  - label: reject the whole file on one malformed line
    rejected_because: |
      CDCP event logs are append-only streams. One bad line should not
      block extraction from the remaining valid events.
rationale: |
  R-TTE-006 extends the existing trace ingestion boundary from one
  failed trace file to a CDCP event stream. The same trust split still
  applies: deterministic code copies explicit fields and writes schema
  valid YAML, while humans approve the behavior before promotion.
evidence:
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/traceability.md
  - kind: decision
    ref: decisions/DEC-TTE-002-failed-trace-becomes-human-reviewed-eval-case.md
rollback: |
  Remove the `from-cdcp-events` CLI command, the adapter module, and
  its fixtures and tests. Existing trace ingest, schema validation,
  and runner behavior remain unchanged.
owner: platform
---

## decision

The CDCP event-log adapter extracts draft eval cases only from
explicit event payload fields on failed gate, review finding, and
incident events. It skips malformed JSONL lines, ignores unsupported
events, and marks every generated case as review-needed before any
promotion to a release gate.

## alternatives

- Infer missing trace facts from event names and notes. Rejected
  because notes can be short or human-written, and the adapter must
  not invent expected behavior.
- Auto-promote event-derived cases. Rejected because a failed gate,
  review finding, or incident is evidence for a draft, not approval
  for a binding suite.
- Reject the whole file on one malformed line. Rejected because CDCP
  event logs are append-only streams and valid later events should
  still be usable.

## rationale

R-TTE-006 extends the existing trace ingestion boundary from one
failed trace file to a CDCP event stream. The same trust split still
applies: deterministic code copies explicit fields and writes schema
valid YAML, while humans approve the behavior before promotion.

## evidence

- `specs/0001-trace-to-eval-harness/requirements.md`
- `specs/0001-trace-to-eval-harness/traceability.md`
- `decisions/DEC-TTE-002-failed-trace-becomes-human-reviewed-eval-case.md`

## rollback

Remove the `from-cdcp-events` CLI command, the adapter module, and
its fixtures and tests. Existing trace ingest, schema validation, and
runner behavior remain unchanged.
