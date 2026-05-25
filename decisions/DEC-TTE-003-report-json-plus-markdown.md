---
id: DEC-TTE-003-report-json-plus-markdown
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-004
date: 2026-05-25
status: approved
reversible: true
decision: |
  Every `run` writes a JSON report and a Markdown report from the
  same result payload. JSON serves CI diffs and downstream tooling;
  Markdown serves pull-request comments and archived review notes.
alternatives:
  - label: JSON only
    rejected_because: |
      Reviewers need a short table that names the failed case,
      suite, trace, and check. JSON-only forces every reviewer to
      pipe through a renderer.
  - label: Markdown only
    rejected_because: |
      CI diffs and downstream tooling need a machine-readable shape.
      Markdown-only loses that.
rationale: |
  One payload, two artifacts is the cheapest contract that serves
  both audiences. The pattern matches the report shape used in
  `mcp-security-lab` and the report shape used by the eval suite in
  `supplier-risk-rag-agent`.
evidence:
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
  - kind: decision
    ref: ../mcp-security-lab/decisions/DEC-MCPSEC-003-json-and-markdown-report-shapes.md
rollback: |
  Remove the Markdown renderer and emit JSON only. The internal
  result payload stays the same; only the artifact set narrows.
owner: platform
---

## decision

Every `run` writes a JSON report and a Markdown report from the same
result payload. JSON serves CI diffs and downstream tooling; Markdown
serves pull-request comments and archived review notes.

## alternatives

- JSON only. Rejected because reviewers need a short table.
- Markdown only. Rejected because CI needs a diffable shape.

## rationale

One payload, two artifacts is the cheapest contract that serves both
audiences. The pattern matches the report shape in `mcp-security-lab`
and the eval suite in `supplier-risk-rag-agent`.

## evidence

- `specs/0001-trace-to-eval-harness/requirements.md`
- `../mcp-security-lab/decisions/DEC-MCPSEC-003-json-and-markdown-report-shapes.md`

## rollback

Remove the Markdown renderer and emit JSON only. The result payload
stays the same.
