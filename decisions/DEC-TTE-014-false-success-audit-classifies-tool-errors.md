---
id: DEC-TTE-014-false-success-audit-classifies-tool-errors
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-029, R-TTE-SCHEMA-007
date: 2026-10-12
status: approved
reversible: true
decision: |
  trace-to-eval-harness adds a `false-success` command that reads the tool
  errors in a trace and gives each one class: repaired when a later call to
  the same tool is not an error, ignored when nothing repairs it and the trace
  claims no success, and proceeded_as_success when nothing repairs it and the
  trace claims success anyway. A separate flag, success_without_effect, fires
  when a trace claims success, made a write-tool call, and recorded an empty
  `effects` list. A success claim is `terminal_state.status` in a listed set or
  an output that contains a listed completion phrase, and the report names the
  rule that fired. The command reads the `terminal_state` and `effects` fields
  that DEC-TTE-013 added to the trace schema; it adds no trace field.
alternatives:
  - label: ask a judge model whether the answer overstates the outcome
    rejected_because: |
      DEC-TTE-001 keeps the gate path deterministic. A judge verdict cannot be
      re-run to the same answer, and the evidence for this failure is already
      structured: an error status on a call and a success status at the end.
  - label: fold the audit into the eval-case runner as a new check type
    rejected_because: |
      A check type needs a reviewed eval case per trace. The audit is meant to
      sweep traces nobody has written a case for yet, and three product repos
      consume the eval-case schema from main, so a new verb is the additive
      change.
  - label: treat a missing `effects` key as an empty list
    rejected_because: |
      Producers that do not emit effects yet would flag every write. Only a
      trace that records `effects` and records nothing is evidence of a
      no-effect success.
rationale: |
  An agent that hits a tool error and then reports success produces the
  failure that pass rates hide, because the run reads as a pass. Epoch AI's
  InnovationEval write-up found agents that claimed higher scores than their
  methods achieved. A trace that already carries tool-call statuses, a
  terminal state, and an effects list holds enough structure to catch the
  plainest form of that claim without a model in the loop.
evidence:
  - kind: code
    ref: trace_to_eval/false_success.py
  - kind: code
    ref: trace_to_eval/cli.py
  - kind: schema
    ref: schemas/false-success-report.schema.json
  - kind: test
    ref: tests/test_false_success.py
  - kind: example
    ref: examples/false_success/
  - kind: example
    ref: reports/false_success.json
  - kind: decision
    ref: decisions/DEC-TTE-013-repeated-runs-grade-state-and-effects.md
  - kind: benchmark
    ref: https://epoch.ai/publications/innovationeval
rollback: |
  Remove the false-success command and module, its schema, the conformance
  mapping, the four example traces, the committed report, and the schema
  fixtures. Restore spec_check to R-TTE-001..028 and R-TTE-SCHEMA-001..006.
  The trace, eval-case, and run-report schemas are unchanged, so no consumer
  needs a matching rollback.
owner: science.proof_gate_runner
systems_map: |
  Tool-call statuses, the terminal state, and the effects list are three
  independent records of the same run. The audit compares them. A disagreement
  between an error record and a success record is the signal, and the claim
  rules stay listed constants so the comparison can be re-run and argued with.
transferable_principle: |
  When a system reports its own outcome, check the report against a record the
  reporter did not write: the tool's own status, the state it left behind, the
  effects it emitted.
falsification_test: |
  Retire the phrase rule if, on a held-out set of real traces, most
  proceeded_as_success flags that fire only on a phrase are false positives on
  review. Retire the command if flagged traces never change a promotion or
  debugging decision beyond what the eval-case runner already reports.
adoption_ladder:
  minimum_viable: |
    Three error classes, one no-effect flag, a versioned report schema, four
    synthetic traces, and a provider-free CLI with an opt-in failing exit.
  mid_adoption: |
    Product repos run the audit over their trace exports in CI with
    `--write-tools` set to their real write surface.
  full_adoption: |
    Promotion logic treats a proceeded_as_success or success_without_effect
    flag as a blocking finding, and flagged traces feed `ingest` as draft
    eval cases for human review.
  monitoring_signals:
    - share of phrase-only flags that survive human review
    - flagged traces that a passing eval-case run did not catch
    - traces skipped by the no-effect flag because `effects` was not recorded
---

# false-success audit classifies tool errors

A run that errored and then said it was done is a failed run that reads as a pass.
