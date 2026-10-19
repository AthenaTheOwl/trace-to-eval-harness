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

## 2026-10-18 — 3c1b3791fec72371317363b7471fee4b00253987 review handoff evidence exercise

- scope: Add three synthetic handoff traces and a reviewer exercise for failed
  verification, a claimed write without recorded effects, and a clean result.
  Exercise the false-success behavior already present on published main.
- proof:
  - pytest — `tests/test_false_success.py::test_review_handoff_examples_check_claims_against_recorded_evidence`,
    `.github/workflows/ci.yml`
  - validate_data_conformance — `schemas/conformance.yaml` (trace mapping for
    `examples/review_handoff/*.json`), `.github/workflows/ci.yml`
  - false-success --fail-on-flag — `examples/review_handoff/README.md`
  - voice_lint, validate_sensitive_disclosures, check_no_bom, spec_check,
    validate_schemas, validate_decisions, validate_roles, validate_tools,
    validate_policies, validate_skills, validate_dreams,
    check_schema_cache_freshness — `.github/workflows/ci.yml`

## 2026-05-25 — pre-CDCP init Trace-To-Eval Package MVP

- scope: Initial MVP commit. Turn failed traces into deterministic regression cases.
- proof:
  - pytest — `.github/workflows/ci.yml`
  - voice_lint — `.github/workflows/ci.yml`
  - spec_check — `.github/workflows/ci.yml`
