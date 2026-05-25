# product.spec-writer

Write the spec ledger for a new change, defining R-TTE-* requirements with one DEC per ID before any package code lands.

## Inputs

- change_request (signal, required=True)
- routing_decision (artifact, required=True)

## Outputs

- spec_ledger (kind=spec, artifact_type=spec, required=True)
- traceability_table (kind=artifact, artifact_type=spec, required=True)

## Boundaries

- forbidden: modify_code
- forbidden: modify_prompts
- forbidden: approve_own_work
- forbidden: deploy_to_production

## Required gates

- voice_lint
- spec_check

## Escalation

- requirement_scope_unclear -> control.coordinator
- existing_decision_conflict -> engineering.code-reviewer
