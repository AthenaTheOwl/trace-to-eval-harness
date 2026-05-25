---
id: DEC-TTE-005-formal-schemas-before-integrations
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-SCHEMA-001
date: 2026-05-25
status: approved
reversible: true
decision: |
  Trace-to-eval publishes versioned JSON Schemas for traces, eval
  cases, and run reports before any judge integration work. The
  validate command gates files against those schemas and keeps the
  deterministic runner as the first release gate.
alternatives:
  - label: infer contracts only from examples
    rejected_because: |
      Examples are useful, but they do not give downstream repos a
      stable machine-checkable contract for trace, eval, or report
      files.
  - label: add judge output fields before schema publication
    rejected_because: |
      Judge fields would add provider-shaped data before the local
      deterministic contract is fixed. That would make later reuse
      depend on vendor and prompt choices.
rationale: |
  R-TTE-SCHEMA-001, R-TTE-SCHEMA-002, R-TTE-SCHEMA-003, and
  R-TTE-SCHEMA-004 all need a stable local contract. Versioned
  schemas and fixtures make the contract testable without network
  calls. Judge checks can be added later as a new deterministic case
  type or schema version.
evidence:
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/traceability.md
  - kind: decision
    ref: decisions/DEC-TTE-001-deterministic-checks-before-llm-judges.md
rollback: |
  Remove the published schema files, the validate command path, and
  the schema fixture gate. Keep the existing ingest and run commands.
  A later DEC can publish a replacement schema set if the file
  contract changes.
owner: platform
---

## decision

Trace-to-eval publishes versioned JSON Schemas for traces, eval
cases, and run reports before any judge integration work. The
validate command gates files against those schemas and keeps the
deterministic runner as the first release gate.

## alternatives

- Infer contracts only from examples. Rejected because examples do
  not give downstream repos a stable machine-checkable contract for
  trace, eval, or report files.
- Add judge output fields before schema publication. Rejected because
  provider-shaped data would enter the contract before the local
  deterministic fields are fixed.

## rationale

R-TTE-SCHEMA-001, R-TTE-SCHEMA-002, R-TTE-SCHEMA-003, and
R-TTE-SCHEMA-004 all need a stable local contract. Versioned schemas
and fixtures make that contract testable without network calls. Judge
checks can be added later as a new deterministic case type or schema
version.

## evidence

- `specs/0001-trace-to-eval-harness/requirements.md`
- `specs/0001-trace-to-eval-harness/traceability.md`
- `decisions/DEC-TTE-001-deterministic-checks-before-llm-judges.md`

## rollback

Remove the published schema files, the validate command path, and the
schema fixture gate. Keep the existing ingest and run commands. A
later DEC can publish a replacement schema set if the file contract
changes.
