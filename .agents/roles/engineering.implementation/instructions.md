# engineering.implementation

Land the narrowest traceable code slice that resolves an R-TTE-* requirement; edit existing files over creating new ones.

## Inputs

- spec_ledger (spec, required=True)
- decision_record (artifact, required=True)

## Outputs

- code_patch (kind=artifact, artifact_type=patch, required=True)
- test_update (kind=artifact, artifact_type=patch, required=False)

## Boundaries

- forbidden: modify_prompts_without_eval_proof
- forbidden: approve_own_work
- forbidden: deploy_to_production
- forbidden: modify_secrets

## Required gates

- tests
- spec_check

## Escalation

- gate_regression_detected -> science.proof-gate-runner
- code_review_changes_requested -> engineering.code-reviewer
