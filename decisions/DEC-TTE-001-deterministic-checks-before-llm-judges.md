---
id: DEC-TTE-001-deterministic-checks-before-llm-judges
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-003
date: 2026-05-25
status: approved
reversible: true
decision: |
  The first release of the eval runner uses deterministic checks
  only: `contains_required_text`, `does_not_contain_text`,
  `citation_span_present`, `tool_call_allowed`, and
  `refusal_required`. No LLM judge runs in the gate path.
alternatives:
  - label: ship an LLM-judge scorer in the MVP
    rejected_because: |
      Judge scores drift across runs and providers. A regression gate
      that depends on a model call also depends on keys, network, and
      provider availability. The package needs to run in CI with no
      vendor key.
  - label: leave checks to repo-specific code
    rejected_because: |
      The point of this package is to be reusable. Repo-specific
      check code defeats reuse and pushes the same boilerplate into
      every consumer.
rationale: |
  Failed traces usually expose concrete evidence: a missing span, a
  disallowed tool, or an answer that should have refused. These can
  be checked deterministically without network calls or random
  scoring drift. The deterministic shell is also the right place to
  layer a judge later: the judge becomes one more check kind that
  composes with the existing five.
evidence:
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
  - kind: spec
    ref: R-TTE-001 (trace JSON model; the check kinds consume the trace fields this requirement defines)
  - kind: decision
    ref: ../supplier-risk-rag-agent/decisions/DEC-EVL-002-deterministic-eval-runs-without-vendor-keys.md
rollback: |
  Remove the runner module that dispatches the five check kinds. The
  trace and case data models remain intact. A later DEC can supersede
  this one to add a judge-based check kind without changing the five
  deterministic kinds.
owner: platform
---

## decision

The first release of the eval runner uses deterministic checks only:
`contains_required_text`, `does_not_contain_text`,
`citation_span_present`, `tool_call_allowed`, and `refusal_required`.
No LLM judge runs in the gate path.

## alternatives

- Ship an LLM-judge scorer in the MVP. Rejected because judge scores
  drift and the gate would depend on keys, network, and provider
  availability.
- Leave checks to repo-specific code. Rejected because the point of
  this package is reuse; per-repo boilerplate defeats that.

## rationale

Failed traces expose concrete evidence: a missing span, a disallowed
tool, or an answer that should have refused. Deterministic checks
hit all of that without network calls or scoring drift. The
deterministic shell also leaves room for a judge as an added check
kind in a later release.

## evidence

- `specs/0001-trace-to-eval-harness/requirements.md`
- `../supplier-risk-rag-agent/decisions/DEC-EVL-002-deterministic-eval-runs-without-vendor-keys.md`

## rollback

Remove the runner module that dispatches the five check kinds. The
trace and case data models remain intact. A later DEC can add a
judge-based check kind without changing the five deterministic kinds.
