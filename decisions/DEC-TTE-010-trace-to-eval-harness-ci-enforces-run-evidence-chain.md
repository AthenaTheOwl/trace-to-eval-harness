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
