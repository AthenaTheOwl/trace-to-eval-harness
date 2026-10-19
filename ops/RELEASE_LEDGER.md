# RELEASE_LEDGER

Every commit on main that represents shippable scope lands here with
date, SHA, title, scope, and proof refs.

## Format

```
## YYYY-MM-DD — <sha> <title>

- scope: <one or two sentences>
- proof:
  - <gate or test name> — <where the proof lives>
```

## Entries

## 2026-10-19 — 2e1a440c5dea6872a5d1b1a7f0a2be2e7276b262 validate review handoff traces in conformance gate

- scope: Add `examples/review_handoff` to the trace mapping so CI checks the
  handoff traces against the trace schema. Corrects the proof refs of the
  2026-10-18 entry below, which are left as published; at 3c1b379 no CI gate
  checked these traces.
- proof:
  - validate_data_conformance — `schemas/conformance.yaml`, `.github/workflows/ci.yml`
  - validate trace — `examples/review_handoff/*.json`
  - pytest — `tests/test_false_success.py::test_review_handoff_examples_check_claims_against_recorded_evidence`
  - false-success --fail-on-flag — `examples/review_handoff/README.md`

## 2026-10-18 — 3c1b3791fec72371317363b7471fee4b00253987 review handoff evidence exercise

- scope: Add three synthetic handoff traces and a reviewer exercise for failed
  verification, a claimed write without recorded effects, and a clean result.
  Exercise the false-success behavior already present on published main.
- proof:
  - pytest — full fresh-main suite and the three-trace classification regression
  - validate trace — all three handoff traces pass the current trace schema
  - false-success --fail-on-flag — exits 1 with two flagged traces, as expected
  - native governance and conformance gates — pass for the scoped source above

## 2026-05-25 — pre-CDCP init Trace-To-Eval Package MVP

- scope: Initial MVP commit. Turn failed traces into deterministic regression cases.
- proof:
  - pytest — `.github/workflows/ci.yml`
  - voice_lint — `.github/workflows/ci.yml`
  - spec_check — `.github/workflows/ci.yml`
