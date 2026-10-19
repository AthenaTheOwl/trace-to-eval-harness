# Review a handoff from its evidence

These synthetic traces model a small author/reviewer workflow. The first author
claims passing tests after collection failed. The second claims a saved file while
the recorded effect list is empty. The third records a write, a read, and a file
effect. Expected audit: two flagged traces, one unflagged trace.

```powershell
python -m trace_to_eval false-success examples/review_handoff --out reports/handoff_audit.json --fail-on-flag
```

Exit 1 is the expected result: `claimed-tests` has `proceeded_as_success` and
`no-observed-write` has `success_without_effect`. The fixture check is part of
`tests/test_false_success.py`. No agent or model runs in this example.

A reviewer should first receive the task, permitted write scope, diff, raw check
output, and recorded effects. It should form an assessment before reading the
author's conclusion. Then reconcile disagreements with explicit evidence refs.
[Audit Without Verification](https://arxiv.org/abs/2609.07680) is the primary
research lead behind this exercise; it studies auditors relaying upstream claims.
The two-pass procedure here is a local design proposal, not a result measured by
this repository.

This audit checks declared trace fields. A fabricated successful tool result or
effect record can still pass. Capture the evidence outside the author process,
bind it to the actual revision, and keep the original failure when recording a
retry. A clean report establishes only that these particular structural flags did
not fire; factual support, authorization and current applicability need separate
checks.
