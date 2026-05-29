---
id: DEC-TTE-010-trace-to-eval-harness-ci-enforces-run-evidence-chain
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-015
date: 2026-05-29
status: approved
reversible: true
amends: DEC-TTE-009-packet-generator-resolves-repo-uris
decision: |
  trace-to-eval-harness CI enforces the DEC-CDCP-015 run-evidence gate
  chain on every pull request and every push to main. The
  .github/workflows/run-evidence-gates.yml workflow runs the universal
  gates that apply to a consumer repo (schema-cache-freshness,
  voice-lint, bom-check, spec-check, decisions-validation, language
  test runner) plus the two harness-specific gates from the contract:
  all-example-packets-validate over every examples/run_evidence/*.packet.json
  and uri-resolver-tests over tests/test_uri.py and tests/test_run_evidence.py.
  No gate carries continue-on-error: true.
alternatives:
  - label: keep ci.yml as the only workflow and bolt the new gates onto it
    rejected_because: |
      ci.yml already runs the universal validators in one big job. Adding
      example-packet validation and the URI resolver split into the same
      job blurs the contract surface. A second workflow named after the
      contract (run-evidence-gates) makes the DEC-CDCP-015 mapping
      legible from the Actions tab and from PR check names.
  - label: gate the example packets via pytest only
    rejected_because: |
      The example packets are evidence artifacts, not test fixtures.
      Validating them through the CLI in CI keeps the consumer surface
      under contract: if the schema bumps or the validate command
      regresses, CI catches it the same way a downstream reviewer would.
  - label: mark the new gates continue-on-error while we settle them
    rejected_because: |
      DEC-CDCP-015 forbids continue-on-error on any contract gate. The
      whole reason the contract exists is so main cannot accept
      unverifiable work; a non-blocking gate defeats that.
rationale: |
  DEC-CDCP-015 (athena-site) locks the CI enforcement contract for the
  CDCP portfolio. trace-to-eval-harness is the consumer side of the
  run-evidence chain: it has no Run records or event ledgers of its
  own, so the producer-side gates (packet-generation-from-canonical-sample,
  packet-validation against a fresh packet, replay-smoke) do not apply
  here. The consumer-side obligation is that every shipped example
  packet validates against the published schema and the URI resolver
  tests stay green. Adding run-evidence-gates.yml lifts those two
  checks out of the general pytest pool and binds them to the contract
  by name, so the CI status maps one-to-one onto DEC-CDCP-015's gate
  list.
evidence:
  - kind: decision
    ref: decisions/DEC-TTE-009-packet-generator-resolves-repo-uris.md
  - kind: workflow
    ref: .github/workflows/run-evidence-gates.yml
  - kind: workflow
    ref: .github/workflows/ci.yml
  - kind: test
    ref: tests/test_uri.py
  - kind: test
    ref: tests/test_run_evidence.py
  - kind: artifact
    ref: examples/run_evidence/
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
rollback: |
  Delete .github/workflows/run-evidence-gates.yml and revert
  scripts/spec_check.py's expected-requirement range back to
  R-TTE-001..014. Drop R-TTE-015..018 from
  specs/0001-trace-to-eval-harness/requirements.md and
  traceability.md. ci.yml stays as the pre-DEC-CDCP-015 baseline; the
  example packets keep validating through pytest's existing
  test_run_evidence.py coverage. The rollback path is bounded because
  the new workflow file is additive and the spec_check.py change is a
  one-line range bump.
owner: science.eval_curator
systems_map: |
  CI as the enforcement boundary for cross-repo contracts. The
  DEC-CDCP-015 contract names the gates; the per-repo workflow file
  binds those gates to GitHub Actions check names; PR check status
  becomes the single observable that says "this contract held on
  this commit." The producer-vs-consumer split in the contract maps
  onto distinct gate subsets per repo role.
transferable_principle: |
  Cross-repo contracts hold only if a named CI check per gate
  blocks merge on failure. A non-blocking gate is a documentation
  artifact, not a contract. Per-repo workflow files named after the
  contract (not after the repo) make the contract mapping legible
  from one place — the Actions tab.
falsification_test: |
  If a PR that violates the run-evidence chain (corrupted example
  packet, broken URI resolver, missing schema cache) merges to main
  without the run-evidence-gates workflow failing, the contract
  binding is falsified. Equivalently: if a gate that was supposed to
  fail passes because of `continue-on-error: true` or a similar
  marker, the enforcement claim is falsified.
adoption_ladder:
  minimum_viable: |
    `run-evidence-gates.yml` workflow exists; runs the two
    consumer-side gates (example-packet validation, URI resolver
    tests); triggers on PR + push to main.
  mid_adoption: |
    Workflow status badge in README; PR check name pinned in
    branch-protection rules; gate failures linked to the DEC-CDCP-015
    gate id in the workflow output.
  full_adoption: |
    All product repos in the portfolio publish their
    role-appropriate `run-evidence-gates.yml`; the portfolio
    manifest in athena-site lists every repo's bound gates; a
    portfolio-status check aggregates green/red across repos.
  monitoring_signals:
    - run-evidence-gates pass/fail rate over rolling 30 days
    - continue-on-error scan exit code (must stay 0)
    - drift between athena-site portfolio-manifest gate list and per-repo workflow
---

## decision

trace-to-eval-harness CI enforces the DEC-CDCP-015 run-evidence gate
chain on every pull request and every push to main (R-TTE-015). The
new `.github/workflows/run-evidence-gates.yml` workflow runs the
universal gates that apply to a consumer repo (schema-cache-freshness,
voice-lint, bom-check, spec-check, decisions-validation, pytest) plus
the two harness-specific gates from the contract:
`all-example-packets-validate` over every
`examples/run_evidence/*.packet.json` (R-TTE-016) and
`uri-resolver-tests` over `tests/test_uri.py` and
`tests/test_run_evidence.py` (R-TTE-017). No gate carries
`continue-on-error: true` (R-TTE-018). The existing `ci.yml` workflow
stays in place as the original CDCP governance gate; the new workflow
adds the consumer-side contract checks alongside it.

This repo is a consumer of the run-evidence chain: it has no Run
records or event ledgers of its own, so the producer-side gates in
the contract (packet-generation-from-canonical-sample,
packet-validation against a fresh packet, replay-smoke) do not apply
here. The consumer obligation is that every shipped example packet
still validates against the published schema and the URI resolver
keeps doing its job.

## alternatives

- Keep `ci.yml` as the only workflow and bolt the new gates onto it.
  Rejected because a separate workflow named after the contract
  (`run-evidence-gates`) makes the DEC-CDCP-015 mapping legible from
  the Actions tab and from PR check names.
- Gate the example packets via pytest only. Rejected because the
  example packets are evidence artifacts, not test fixtures.
  Validating them through the CLI in CI keeps the consumer surface
  under contract: if the schema bumps or the validate command
  regresses, CI catches it the same way a downstream reviewer would.
- Mark the new gates `continue-on-error` while we settle them.
  Rejected because DEC-CDCP-015 forbids `continue-on-error: true` on
  any contract gate.

## rationale

DEC-CDCP-015 in athena-site locks the CI enforcement contract for the
CDCP portfolio. The contract draws a line between "we have artifacts"
and "main cannot accept unverifiable work" and puts that line in
GitHub Actions. trace-to-eval-harness is the consumer side of the
run-evidence chain. Its piece of the contract is: every shipped
example packet validates, and the URI resolver tests stay green.

`run-evidence-gates.yml` lifts those two checks out of the general
pytest pool and binds them to the contract by name. The CI status
maps one-to-one onto DEC-CDCP-015's gate list, so a future reader of
this repo can confirm contract compliance by reading one workflow
file.

## evidence

- `decisions/DEC-TTE-009-packet-generator-resolves-repo-uris.md`
- `.github/workflows/run-evidence-gates.yml`
- `.github/workflows/ci.yml`
- `tests/test_uri.py`
- `tests/test_run_evidence.py`
- `examples/run_evidence/`
- `specs/0001-trace-to-eval-harness/requirements.md`

## rollback

Delete `.github/workflows/run-evidence-gates.yml` and revert
`scripts/spec_check.py`'s expected-requirement range back to
`R-TTE-001..014`. Drop `R-TTE-015..018` from
`specs/0001-trace-to-eval-harness/requirements.md` and
`traceability.md`. `ci.yml` stays as the pre-DEC-CDCP-015 baseline;
the example packets keep validating through pytest's existing
`test_run_evidence.py` coverage. The rollback path is bounded because
the new workflow file is additive and the `spec_check.py` change is a
one-line range bump.
