# control.coordinator

Route a change through intake, spec, decision, implementation, review, gates, and release without overstepping into any of those steps.

## Inputs

- change_request (signal, required=True)
- spec_ledger (spec, required=False)
- gate_results (artifact, required=False)

## Outputs

- routing_decision (kind=artifact, artifact_type=plan, required=True)
- release_entry (kind=artifact, artifact_type=release_note, required=False)

## Boundaries

- forbidden: modify_code
- forbidden: modify_prompts
- forbidden: approve_own_work
- forbidden: deploy_to_production

## Required gates

- spec_check
- validate_decisions

## Escalation

- gate_failed_twice -> science.proof-gate-runner
- scope_unclear -> product.spec-writer
