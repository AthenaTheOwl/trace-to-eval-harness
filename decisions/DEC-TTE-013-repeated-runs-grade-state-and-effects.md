---
id: DEC-TTE-013-repeated-runs-grade-state-and-effects
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-027, R-TTE-028, R-TTE-SCHEMA-006
date: 2026-08-27
status: approved
reversible: true
decision: |
  trace-to-eval-harness grades structured terminal state and effects in
  addition to answer text, then aggregates ordered run reports into pass@1,
  pass@k, pass^k, stability, and missing-attempt measures. Missing cases
  consume an attempt slot and fail that slot. The first supplied report is
  attempt one, so the aggregation remains deterministic and inspectable.
alternatives:
  - label: keep one run report as the only verdict
    rejected_because: |
      One report cannot distinguish a stable case from a lucky trajectory.
      It also rewards a runner that silently omits a case on a later attempt.
  - label: average check pass rates across attempts
    rejected_because: |
      An average can hide one critical case that fails intermittently. The
      case-level pass^k measure keeps that failure visible.
  - label: grade only the final answer
    rejected_because: |
      A correct sentence can accompany the wrong stored state or an unrelated
      side effect. Those outcomes need separate deterministic checks.
rationale: |
  Stateful agents operate on systems whose durable state matters more than a
  fluent completion. Repeated execution also exposes unstable behavior that a
  first attempt cannot measure. The new checks and report stay deterministic,
  provider-free, and small enough to run in ordinary CI.
evidence:
  - kind: code
    ref: trace_to_eval/runner.py
  - kind: code
    ref: trace_to_eval/reliability.py
  - kind: schema
    ref: schemas/reliability-report.schema.json
  - kind: test
    ref: tests/test_runner.py
  - kind: test
    ref: tests/test_reliability.py
  - kind: example
    ref: reports/reliability.json
rollback: |
  Remove the two structured check types, the reliability command and module,
  the reliability schema and fixtures, and the committed repeated-run example.
  Restore trace, eval-case, and run-report schemas to version 1.0.0.
owner: science.proof_gate_runner
systems_map: |
  Structured trace state and effects feed deterministic per-attempt checks.
  Ordered run reports feed the reliability aggregate. The aggregate gives
  promotion logic a case-level stability signal without changing the runner
  that produced the attempts.
transferable_principle: |
  Any workflow that mutates durable state should grade the state, its residue,
  and repeated execution separately from answer text.
falsification_test: |
  Retire the new aggregate if a held-out cohort shows that pass^k never changes
  a promotion or debugging decision beyond first-pass rate, or if independent
  consumers cannot reproduce the report from the same ordered inputs.
adoption_ladder:
  minimum_viable: |
    Two state checks, a versioned reliability schema, three attempt fixtures,
    and a provider-free CLI report.
  mid_adoption: |
    Product repos emit terminal state and structured effects, and CI records
    pass^3 for critical stateful cases.
  full_adoption: |
    Factory admission consumes signed repeated-run reports, stratified by task
    class and harness hash, with explicit cost and stability thresholds.
  monitoring_signals:
    - pass^k changes a promotion or debugging decision on a held-out cohort
    - missing attempts remain visible in every aggregate
    - independent consumers reproduce the report from the same ordered inputs
---

# repeated runs grade state and effects

The first run remains useful. It no longer gets to speak for the next nineteen.
