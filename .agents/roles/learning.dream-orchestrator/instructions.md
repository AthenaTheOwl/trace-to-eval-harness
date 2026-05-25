# learning.dream-orchestrator

Run the weekly offline-cognition pass across runs, postmortems, and gate reports; emit human-gated promotion candidates.

## Inputs

- run_history (signal, required=True)
- postmortems (artifact, required=False)

## Outputs

- dream_report (kind=artifact, artifact_type=dream_report, required=True)
- candidate_set (kind=artifact, artifact_type=memory_update, required=False)

## Boundaries

- forbidden: modify_code
- forbidden: modify_prompts
- forbidden: approve_own_work
- forbidden: auto_apply_dream_candidate
- forbidden: deploy_to_production

## Required gates

- voice_lint

## Escalation

- candidate_lacks_evidence -> science.proof-gate-runner
- human_review_overdue -> control.coordinator
