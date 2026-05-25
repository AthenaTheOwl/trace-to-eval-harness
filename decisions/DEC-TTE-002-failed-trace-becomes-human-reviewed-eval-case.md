---
id: DEC-TTE-002-failed-trace-becomes-human-reviewed-eval-case
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-002
date: 2026-05-25
status: approved
reversible: true
decision: |
  The `ingest` command turns one failed trace into one draft eval
  case YAML. The draft carries human-review fields and TODO markers;
  it never lands as a binding gate case until a human edits and
  approves it.
alternatives:
  - label: auto-promote ingested cases to the gate suite
    rejected_because: |
      A failed trace is evidence, not a verdict. Auto-promoting
      would let one bad answer set the policy for every future run.
      The eval suite needs human judgment on what counts as correct.
  - label: leave case authoring to humans entirely
    rejected_because: |
      Most of the work to author a case is mechanical: copy the
      trace id, write the input, write the expected output. Forcing
      a human to do that work twice (once when reviewing the trace,
      once when writing the YAML) wastes the evidence already in
      hand.
rationale: |
  Half the work is mechanical, half is judgment. Splitting on that
  boundary keeps the package useful immediately (mechanical work
  done) while preserving the review friction that makes gate cases
  trustworthy. The TODO markers force the human to read the draft
  rather than rubber-stamp it.
evidence:
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
  - kind: doc
    ref: examples/eval_cases.yaml
rollback: |
  Remove the `ingest` command. The data models and the runner
  continue to work against hand-authored case YAML. No state changes
  outside the consumer's repo are required.
owner: platform
---

## decision

The `ingest` command turns one failed trace into one draft eval case
YAML. The draft carries human-review fields and TODO markers; it
never lands as a binding gate case until a human edits and approves
it.

## alternatives

- Auto-promote ingested cases to the gate suite. Rejected because a
  failed trace is evidence, not a verdict.
- Leave case authoring to humans entirely. Rejected because the
  mechanical work (trace id, input, output) is already in hand.

## rationale

Half the work is mechanical, half is judgment. Splitting on that
boundary keeps the package useful immediately while preserving the
review friction that makes gate cases trustworthy.

## evidence

- `specs/0001-trace-to-eval-harness/requirements.md`
- `examples/eval_cases.yaml`

## rollback

Remove the `ingest` command. The runner continues to work against
hand-authored case YAML.
