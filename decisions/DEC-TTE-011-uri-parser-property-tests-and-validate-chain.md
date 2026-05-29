---
id: DEC-TTE-011-uri-parser-property-tests-and-validate-chain
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-019
date: 2026-05-29
status: approved
reversible: true
amends: DEC-TTE-010-trace-to-eval-harness-ci-enforces-run-evidence-chain
decision: |
  trace-to-eval-harness adds three hardening pieces on top of the
  DEC-CDCP-015 contract chain: Hypothesis-driven property tests for the
  Round 6 URI parser, a single validate-chain CLI subcommand that runs
  the full ledger -> packet -> cross-check pipeline in one shot, and an
  append-only audit log under ops/audit-log.jsonl with an audit summary
  subcommand for usage aggregation. Property tests run over the URI
  grammar exhaustively rather than against curated examples; the
  validate-chain command collapses four CI steps into one for dev
  workflows and CI alike; the audit log keeps a per-machine trail of
  contract-command invocations.
alternatives:
  - label: rely on the existing example-test pass for URI coverage
    rejected_because: |
      The current tests/test_uri.py covers happy paths and a handful of
      curated malformed inputs. The grammar has corners (uppercase repo
      leading char, 39-vs-41-byte SHA off-by-ones, empty repo, missing
      slash before path) where a regex bug would slip through curated
      coverage. Property tests sweep the grammar; the regex either
      holds on every well-formed input or fails loudly.
  - label: extend the existing evidence subparser instead of adding a top-level validate-chain
    rejected_because: |
      validate-chain is its own contract surface: it runs four stages
      in sequence and produces a single OK or FAIL report. Burying it
      under evidence keeps the subcommand tree balanced but hides the
      most-used command in CI behind a longer invocation. Putting it
      at the top level matches how it will be called from
      run-evidence-gates.yml and dev shells.
  - label: skip the audit log
    rejected_because: |
      Without a usage trail there is no way to answer "how often has
      anyone actually run validate-chain on the canonical ledger." The
      audit log is cheap (one JSONL line per invocation), gitignored
      (no repo bloat), and unlocks the audit summary subcommand that
      tells the operator at a glance whether the CLI is being used.
rationale: |
  DEC-TTE-009 landed the URI resolver; DEC-TTE-010 bound the
  consumer-side gates to CI. The remaining gap was sharpness on the
  parser's grammar and a single-command entry point for the full
  contract chain. The Hypothesis property tests close the URI gap:
  parse + reconstruct + parse is identity for every well-formed input,
  and malformed inputs in every documented failure mode (short SHA,
  long SHA, missing at-sign, missing slash, uppercase repo, empty
  repo, digit-leading repo) reject deterministically. The
  validate-chain subcommand replaces the four-step run-events ->
  validate-packet -> check-record -> diff-summary dance with one
  command that names the failing stage; the cross-checks turn what
  used to be three separate CI assertions into one named check.
  The audit log is the smallest possible usage trail: a JSONL append
  per successful invocation of evidence.from-cdcp-events and
  validate-chain, with a summary subcommand that aggregates by
  command, by result, and by ledger path. The log is gitignored so
  it does not bloat the repo; ops/audit-log.example.jsonl is checked
  in as a shape reference.
evidence:
  - kind: decision
    ref: decisions/DEC-TTE-010-trace-to-eval-harness-ci-enforces-run-evidence-chain.md
  - kind: code
    ref: trace_to_eval/uri.py
  - kind: code
    ref: trace_to_eval/validate_chain.py
  - kind: code
    ref: trace_to_eval/audit.py
  - kind: code
    ref: trace_to_eval/cli.py
  - kind: test
    ref: tests/test_uri_properties.py
  - kind: test
    ref: tests/test_validate_chain.py
  - kind: test
    ref: tests/test_audit.py
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
rollback: |
  Delete tests/test_uri_properties.py, trace_to_eval/validate_chain.py,
  tests/test_validate_chain.py, trace_to_eval/audit.py, and
  tests/test_audit.py. Drop the validate-chain and audit subparsers
  from trace_to_eval/cli.py and revert the audit-entry append on the
  evidence.from-cdcp-events success path. Drop R-TTE-019..022 from
  specs/0001-trace-to-eval-harness/requirements.md and traceability.md.
  Remove ops/audit-log.jsonl from .gitignore and ops/audit-log.example.jsonl
  from disk. The pieces are additive: removing them leaves
  DEC-TTE-009 and DEC-TTE-010 untouched.
owner: science.eval_curator
---

## decision

trace-to-eval-harness adds three hardening pieces on top of the
DEC-CDCP-015 contract chain.

Hypothesis-driven property tests for the Round 6 URI parser
(R-TTE-019). The tests sweep the grammar of
`repo://<repo>@<sha>/<path>` and `artifact://<repo>/<id>`: every
well-formed URI round-trips through `parse_repo_uri` /
`parse_artifact_uri`, and every documented failure mode (short SHA,
long SHA, missing `@`, missing path slash, uppercase repo, empty
repo, digit-leading repo) rejects deterministically.

A single `validate-chain` CLI subcommand (R-TTE-020) that runs the
full DEC-CDCP-015 chain end-to-end: validate every event in the
ledger against the cached `event.schema.json`, locate the producer
Run record, regenerate the packet via the existing pipeline,
re-validate the packet against `run-evidence.schema.json`, then run
four cross-checks (`prompt_snapshot_hash`,
`tool_schemas_snapshot_hash`, `gate_results_summary`,
`fields_populated`) across packet, Run record, and ledger. The OK
path prints a JSON summary; the FAIL path names the failing stage.

An append-only audit log under `ops/audit-log.jsonl` (R-TTE-021)
hooked into successful invocations of `evidence from-cdcp-events`
and `validate-chain`, plus an `audit summary` subcommand
(R-TTE-022) that aggregates the log by command, by result, and by
top ledger paths. The log file is gitignored;
`ops/audit-log.example.jsonl` is checked in as a shape reference.

## alternatives

- Rely on the existing example tests for URI coverage. Rejected
  because curated example sets miss grammar corners (off-by-one SHA
  length, uppercase leading char, missing slash). Property tests
  cover the grammar exhaustively.
- Extend the `evidence` subparser instead of adding a top-level
  `validate-chain`. Rejected because `validate-chain` is its own
  contract surface — four stages, one OK-or-FAIL report — and CI
  workflows call it by name. Top-level placement matches the
  invocation pattern.
- Skip the audit log. Rejected because without a usage trail there
  is no answer to "is anyone actually running this." The log is
  cheap (one JSONL line per call), gitignored (no repo bloat), and
  unlocks the `audit summary` subcommand.

## rationale

DEC-TTE-009 landed the URI resolver; DEC-TTE-010 bound the
consumer-side gates to CI. The remaining gap was sharpness on the
parser's grammar and a single-command entry point for the full
contract chain.

The Hypothesis property tests close the URI gap: 14 tests over the
URI grammar, including parse + reconstruct identity round-trips and
malformed-input rejection across every documented failure mode.

The `validate-chain` subcommand replaces the four-step
run-events -> validate-packet -> check-record -> diff-summary dance
with one command. The cross-checks turn what used to be three
separate CI assertions into one named check; when a stage fails,
the report names it (`event-schema`, `run-record`,
`packet-schema`, `cross-check.prompt_snapshot_hash`,
`cross-check.gate_results_summary`, ...).

The audit log is the smallest possible usage trail: a JSONL append
per successful invocation, with `audit summary` aggregating by
command, by result, and by ledger path. The log is gitignored so
it does not bloat the repo; the example file is checked in as a
shape reference.

## evidence

- `decisions/DEC-TTE-010-trace-to-eval-harness-ci-enforces-run-evidence-chain.md`
- `trace_to_eval/uri.py`
- `trace_to_eval/validate_chain.py`
- `trace_to_eval/audit.py`
- `trace_to_eval/cli.py`
- `tests/test_uri_properties.py`
- `tests/test_validate_chain.py`
- `tests/test_audit.py`
- `specs/0001-trace-to-eval-harness/requirements.md`

## rollback

Delete `tests/test_uri_properties.py`,
`trace_to_eval/validate_chain.py`, `tests/test_validate_chain.py`,
`trace_to_eval/audit.py`, and `tests/test_audit.py`. Drop the
`validate-chain` and `audit` subparsers from `trace_to_eval/cli.py`
and revert the audit-entry append on the `evidence.from-cdcp-events`
success path. Drop `R-TTE-019..022` from
`specs/0001-trace-to-eval-harness/requirements.md` and
`traceability.md`. Remove `ops/audit-log.jsonl` from `.gitignore`
and `ops/audit-log.example.jsonl` from disk. The pieces are
additive: removing them leaves DEC-TTE-009 and DEC-TTE-010
untouched.
