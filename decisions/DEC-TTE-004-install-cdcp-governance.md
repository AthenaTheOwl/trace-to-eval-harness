---
id: DEC-TTE-004-install-cdcp-governance
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-005
date: 2026-05-25
status: approved
reversible: true
decision: |
  Install the Cognitive Delivery Control Plane governance scaffold
  in `trace-to-eval-harness` to match the portfolio baseline. The
  pass adds `.agents/` (AGENTS.md, CATALOG.md, six role contracts,
  tool registry, policy files, state machines, workflows), `dreams/`,
  `ops/` (RELEASE_LEDGER, RESET_LEDGER, event-log, schemas-cache),
  decision-index files under `decisions/`, and seven new gate scripts
  under `scripts/`.
alternatives:
  - label: stay on CDCP-lite (specs + DECs + voice_lint + spec_check)
    rejected_because: |
      CDCP-lite carries no executable shape check on DECs, roles,
      tools, or policies. This package is meant to be reused across
      every other product repo; the scaffold is part of the
      reusability claim.
  - label: defer the install until artifact volume forces it
    rejected_because: |
      Reusable packages spread their conventions to every consumer.
      Lite-shape conventions would spread the gap. Installing the
      full discipline now keeps the conventions correct.
rationale: |
  This repo is the "improvement face" of the agent factory. It
  packages the eval-as-PR-gate pattern so every other repo can adopt
  it. The discipline shown in this repo's scaffolding is itself the
  pattern other repos will inherit. The same gate scripts that catch
  DEC shape drift in `supplier-risk-rag-agent` now run here, which
  means consumers of this package see the full set when they wire it
  up.
evidence:
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
  - kind: decision
    ref: ../supplier-risk-rag-agent/decisions/DEC-CDCP-001-install-cdcp-governance.md
  - kind: doc
    ref: ../athena-site/ops/control-plane.md
  - kind: doc
    ref: ops/schemas-cache/decision.schema.json
rollback: |
  Revert this commit. The added directories (`.agents/`, `dreams/`,
  `ops/`) and the new gate scripts under `scripts/` can be removed
  wholesale. The product code under `trace_to_eval/` and the existing
  CI workflow continue to function with only `spec_check` and
  `voice_lint`. The three pre-install DECs reverted to the lite shape
  can carry the front-matter rewrite forward; no data loss.
owner: platform
---

## decision

Install the Cognitive Delivery Control Plane governance scaffold in
`trace-to-eval-harness` to match the portfolio baseline.

## alternatives

- Stay on CDCP-lite. Rejected because this package is meant to be
  reused across every other product repo; the scaffold is part of
  the reusability claim.
- Defer the install. Rejected because reusable packages spread their
  conventions; lite-shape conventions would spread the gap.

## rationale

This repo is the improvement face of the agent factory. It packages
the eval-as-PR-gate pattern. The discipline shown in the scaffolding
is itself the pattern other repos will inherit.

## evidence

- `specs/0001-trace-to-eval-harness/requirements.md`
- `../supplier-risk-rag-agent/decisions/DEC-CDCP-001-install-cdcp-governance.md`
- `../athena-site/ops/control-plane.md`
- `ops/schemas-cache/decision.schema.json`

## rollback

Revert this commit. The added directories and gate scripts can be
removed wholesale. The existing CI workflow continues to function
with only `spec_check` and `voice_lint`.
