# .agents/CATALOG.md

Index of every role, tool, policy, state machine, and workflow
registered under `.agents/`. The `validate_*.py` scripts in
`scripts/` walk these files and validate each against the cross-repo
schema set from athena-site.

## Roles (6)

| ID | Guild | Mission |
|---|---|---|
| `control.coordinator` | control | Route a change through the workflow without overstepping into any step. |
| `product.spec-writer` | product | Write the spec ledger and one DEC per R-* before any code lands. |
| `engineering.implementation` | engineering | Land the narrowest traceable code slice. |
| `engineering.code-reviewer` | engineering | Read the diff against the spec and the DEC; never edit code. |
| `science.proof-gate-runner` | science | Own the python governance gates and the pytest suite. |
| `learning.dream-orchestrator` | learning | Run the weekly offline-cognition pass; emit human-gated promotion candidates. |

Each role folder under `.agents/roles/<id>/` carries:

- `role.yaml` — schema-validated contract.
- `instructions.md` — narrative for human and agent readers.
- `tools.yaml` — the role's allowed tool subset.
- `gates.yaml` — the gates the role's run must pass.
- `output.schema.json` — the schema for the role's primary output.

## Tools

Tools live in `.agents/tools.yaml`. Twelve tools are registered:
`repo.read`, `repo.apply_patch`, `tests.run`,
`gates.run_voice_lint`, `gates.run_spec_check`,
`gates.run_validate_decisions`, `gates.run_validate_roles`,
`gates.run_validate_tools`, `gates.run_validate_policies`,
`dream.read_recent_commits`, `dream.write_candidate`.

## Policies

Policies live in `.agents/policies/`. Five policies are registered:

- `default-deny.yaml` (priority 0)
- `coordinator-routing-only.yaml` (priority 100)
- `reviewer-cannot-edit-code.yaml` (priority 100)
- `implementation-can-edit-code.yaml` (priority 50)
- `dream-candidates-require-human-approval.yaml` (priority 200)

## State machines

State machines live in `.agents/state-machines/`. Three lifecycles:

- `spec-lifecycle.yaml`
- `run-lifecycle.yaml`
- `release-lifecycle.yaml`

## Workflows

Workflows live in `.agents/workflows/`. Three declarations:

- `single-change.yaml`
- `weekly-dream.yaml`
- `incident-response.yaml`

## Skills

Skills live in `.agents/skills/<id>/SKILL.md`. None graduated yet.
The directory is empty; `validate_skills.py` exits 0 cleanly.

## Deferred catalog (44 roles, future graduations)

The cross-repo control-plane charter at
`../athena-site/ops/control-plane.md` reserves a 44-role catalog
across twelve guilds. The six roles above are the minimum-viable set
this repo runs. Future graduations land here when an R-* requirement
needs a role not yet installed.
