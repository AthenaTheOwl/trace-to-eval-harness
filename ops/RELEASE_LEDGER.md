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

## 2026-05-25 — pre-CDCP init Trace-To-Eval Package MVP

- scope: Initial MVP commit. Turn failed traces into deterministic regression cases.
- proof:
  - pytest — `.github/workflows/ci.yml`
  - voice_lint — `.github/workflows/ci.yml`
  - spec_check — `.github/workflows/ci.yml`
