---
id: DEC-TTE-012-systems-thinking-discipline-adoption
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-023..026
date: 2026-05-29
status: approved
reversible: true
amends: DEC-TTE-011-uri-parser-property-tests-and-validate-chain
decision: |
  trace-to-eval-harness adopts the systems-thinking discipline that
  DEC-CDCP-020 in athena-site established for the portfolio. The
  cached cross-repo schemas (decision, dream-output, run) refresh to
  the post-DEC-CDCP-020 shape so the four new optional fields
  (systems_map, transferable_principle, falsification_test,
  adoption_ladder) round-trip through this repo's validators.
  .agents/AGENTS.md gains a top-level section naming the discipline.
  scripts/validate_decisions.py emits a non-blocking stderr warning
  when a DEC with status: approved is missing any of the four
  fields; exit code stays 0 during the bootstrap window.
  DEC-TTE-009, DEC-TTE-010, and DEC-TTE-011 are retrofitted with
  substantive content in all four fields as the demonstration. The
  earlier DECs (001..008) stay un-retrofitted and surface as
  warnings; the 30-day amendment will ratchet the warning to a hard
  failure for new DECs only.
alternatives:
  - label: refresh the cache and stop there
    rejected_because: |
      A schema cache refresh without an AGENTS.md update and a
      validator extension is a half-adoption. New DEC authors would
      see no signal that the four fields are expected; existing
      DECs would carry no demonstration of what good content looks
      like. The discipline lives in the artifact loop (schema +
      AGENTS.md + validator + retrofit), not in the schema alone.
  - label: retrofit every existing DEC in this repo, not just the last three
    rejected_because: |
      Eleven retrofits in one pass invites copy-paste fatigue and
      content that does not earn the four fields. Three retrofits
      with substantive content set the bar; the warning surfaces
      the rest of the backlog so future passes can address them
      with care. The 30-day amendment is the structural mechanism
      for closing the gap, not a one-shot retrofit sweep.
  - label: make the validator fail on missing fields immediately
    rejected_because: |
      DEC-CDCP-020 explicitly chose the warning-then-ratchet
      sequence (bootstrap-friendly). A hard failure now would
      bounce every in-flight branch and force a backfill sweep
      across the older DECs before any new work could land. The
      30-day amendment exists to make the contract real once the
      norm has taken hold organically.
rationale: |
  Phase 1 in athena-site amended the three cross-repo schemas with
  the four optional fields. Phase 2 (this DEC) lands the same
  discipline in trace-to-eval-harness by refreshing the schema
  cache, updating AGENTS.md, extending the DEC validator with a
  non-blocking warning, retrofitting the three most-recent DECs,
  and recording the adoption as DEC-TTE-012. The same four-step
  pattern (cache -> AGENTS.md -> validator -> retrofit) generalizes
  to every future portfolio-wide schema discipline; this DEC names
  that pattern so the next adoption pass has a template.
evidence:
  - kind: decision
    ref: decisions/DEC-TTE-011-uri-parser-property-tests-and-validate-chain.md
  - kind: schema
    ref: ops/schemas-cache/decision.schema.json
  - kind: schema
    ref: ops/schemas-cache/dream-output.schema.json
  - kind: schema
    ref: ops/schemas-cache/run.schema.json
  - kind: code
    ref: scripts/validate_decisions.py
  - kind: doc
    ref: .agents/AGENTS.md
  - kind: decision
    ref: decisions/DEC-TTE-009-packet-generator-resolves-repo-uris.md
  - kind: decision
    ref: decisions/DEC-TTE-010-trace-to-eval-harness-ci-enforces-run-evidence-chain.md
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
rollback: |
  Revert the schemas-cache files to their pre-DEC-CDCP-020 shape
  (the four optional fields drop out of decision.schema.json,
  dream-output.schema.json, run.schema.json). Drop the
  systems_thinking_warnings helper and its call site from
  scripts/validate_decisions.py. Remove the systems-thinking
  section from .agents/AGENTS.md. Strip the four fields from
  DEC-TTE-009, DEC-TTE-010, DEC-TTE-011 front-matter. Drop
  R-TTE-023..026 from requirements.md and traceability.md. The
  schemas-cache freshness gate will fail until athena-site reverts
  its own copies; the rollback path therefore presumes a
  coordinated revert with athena-site rather than a unilateral
  rollback in this repo.
owner: science.eval_curator
systems_map: |
  Per-repo adoption of cross-repo control-plane discipline; the
  schema cache is the contract, AGENTS.md is the readme, the
  validator is the enforcement, the retrofit is the demonstration.
  Four moves land a portfolio-wide norm in one repo without
  bouncing in-flight work.
transferable_principle: |
  Any cross-repo schema discipline lands via the same four-step
  pattern: cache the schema, name the discipline in AGENTS.md,
  extend the validator with a non-blocking warning, demonstrate
  with retrofits on the recent decisions. Future portfolio-wide
  schemas (Round 7 URI deprecation, Round 8 event-payload
  amendments) repeat the pattern.
falsification_test: |
  If new DECs in this repo over a rolling 30-day window populate
  the four fields at <20% rate despite the validator warning, the
  discipline is not taking hold in this repo and the
  warning-to-failure ratchet should pause for trace-to-eval-harness
  specifically. Equivalently: if the retrofitted fields on DEC-009
  / DEC-010 / DEC-011 drift out of correspondence with the actual
  behavior of those decisions over 90 days (e.g. the
  falsification_test claim is observed and ignored), the
  retrofit-as-demonstration premise is falsified.
adoption_ladder:
  minimum_viable: |
    Schema cache refreshed; validator emits warnings; AGENTS.md
    names the discipline.
  mid_adoption: |
    Last three DECs retrofitted; new DECs populate fields
    organically; warning count trends downward.
  full_adoption: |
    Validator fails on missing fields for new DECs;
    >=80% of historical DECs in this repo retrofitted; the
    four-step pattern is referenced in this DEC's
    transferable_principle as the template for future adoptions.
  monitoring_signals:
    - new-DEC field-population rate per week
    - validator warning count trend over rolling 30 days
    - cross-repo schema-cache drift exit code
---

## decision

trace-to-eval-harness adopts the systems-thinking discipline that
`DEC-CDCP-020` in athena-site established for the portfolio
(R-TTE-023). The cached cross-repo schemas (`decision.schema.json`,
`dream-output.schema.json`, `run.schema.json`) refresh to the
post-DEC-CDCP-020 shape so the four new optional fields
(`systems_map`, `transferable_principle`, `falsification_test`,
`adoption_ladder`) round-trip through this repo's validators.

`.agents/AGENTS.md` gains a top-level section naming the discipline
(R-TTE-024). `scripts/validate_decisions.py` emits a non-blocking
stderr warning when a DEC with `status: approved` is missing any of
the four fields; exit code stays 0 during the bootstrap window
(R-TTE-025). The 30-day amendment will ratchet the warning to a
hard failure for new DECs only.

`DEC-TTE-009`, `DEC-TTE-010`, and `DEC-TTE-011` are retrofitted
with substantive content in all four fields as the demonstration
(R-TTE-026). Earlier DECs (`DEC-TTE-001..008`) stay un-retrofitted
and surface as warnings; the warning makes the backlog visible
without bouncing in-flight work.

## alternatives

- Refresh the cache and stop. Rejected because a cache refresh
  without an AGENTS.md update and validator extension is a
  half-adoption: new DEC authors see no signal that the four
  fields are expected, and existing DECs carry no demonstration
  of what good content looks like.
- Retrofit every DEC in one pass. Rejected because eleven
  retrofits in one sitting invites copy-paste content that does
  not earn the four fields. Three retrofits with care set the
  bar; the warning surfaces the rest of the backlog.
- Hard-fail on missing fields from day one. Rejected because
  DEC-CDCP-020 explicitly chose the warning-then-ratchet sequence.
  A hard failure now would bounce every in-flight branch.

## rationale

Phase 1 in athena-site amended the three cross-repo schemas with
the four optional fields. Phase 2 (this DEC) lands the same
discipline in trace-to-eval-harness via the four-step pattern:
cache the schema, name the discipline in AGENTS.md, extend the
validator with a non-blocking warning, retrofit the recent DECs as
demonstrations. The same pattern generalizes to every future
portfolio-wide schema discipline; this DEC names the pattern so
the next adoption pass has a template.

## evidence

- `decisions/DEC-TTE-011-uri-parser-property-tests-and-validate-chain.md`
- `ops/schemas-cache/decision.schema.json`
- `ops/schemas-cache/dream-output.schema.json`
- `ops/schemas-cache/run.schema.json`
- `scripts/validate_decisions.py`
- `.agents/AGENTS.md`
- `decisions/DEC-TTE-009-packet-generator-resolves-repo-uris.md`
- `decisions/DEC-TTE-010-trace-to-eval-harness-ci-enforces-run-evidence-chain.md`
- `specs/0001-trace-to-eval-harness/requirements.md`

## rollback

Revert the schemas-cache files to their pre-DEC-CDCP-020 shape.
Drop the `systems_thinking_warnings` helper and its call site
from `scripts/validate_decisions.py`. Remove the systems-thinking
section from `.agents/AGENTS.md`. Strip the four fields from
`DEC-TTE-009`, `DEC-TTE-010`, `DEC-TTE-011` front-matter. Drop
`R-TTE-023..026` from `requirements.md` and `traceability.md`.
The schemas-cache freshness gate will fail until athena-site
reverts its own copies; the rollback path therefore presumes a
coordinated revert with athena-site rather than a unilateral
rollback in this repo.
