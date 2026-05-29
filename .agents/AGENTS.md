# .agents/AGENTS.md

The single contract a coding agent (Claude, Codex, or other) reads
before acting on this repo. Specs name what we build. Decisions name
why. This file names how the agent behaves while building.

## Systems-thinking discipline (per DEC-CDCP-020)

Per `DEC-CDCP-020` in athena-site, every substantive DEC, dream
candidate, and Run record in this repo SHOULD carry four fields:

- `systems_map`: what underlying mechanism does this expose?
- `transferable_principle`: what generalizes beyond this decision?
- `falsification_test`: what would prove this wrong?
- `adoption_ladder`: `minimum_viable` -> `mid_adoption` ->
  `full_adoption` plus `monitoring_signals`.

All four fields are optional in the schema. `validate_decisions.py`
emits a warning to stderr when a new DEC with `status: approved` is
missing any of them; exit code stays 0. After 30 days, the warning
ratchets to a hard failure via amendment DEC.

For pure-design choices where a falsification test does not apply,
set the field to `"Pure-design choice; falsification test not
applicable."` rather than leaving it blank.

## Coding style

- Python 3.11. Install with `python -m pip install -e ".[dev]"`.
- pytest for tests. The `pyproject.toml` pins the toolchain.
- Edit existing files. Use the `Edit` tool over `Write` when the file
  already exists; `Write` rewrites the whole file and risks losing
  context. Reserve `Write` for new files.
- The runner uses deterministic checks only per
  `DEC-TTE-001-deterministic-checks-before-llm-judges`. No LLM judge
  in the gate path.
- The ingest command writes drafts. A draft eval case never lands as
  a binding gate case without human review per
  `DEC-TTE-002-failed-trace-becomes-human-reviewed-eval-case`.

## Domain decisions

- Deterministic checks before LLM judges. Five check kinds:
  `contains_required_text`, `does_not_contain_text`,
  `citation_span_present`, `tool_call_allowed`, `refusal_required`.
- Failed trace becomes a human-reviewed draft eval case. TODO
  markers force a real read before merge.
- Report JSON plus Markdown shapes. One payload, two artifacts.
- Voice rules in `scripts/voice_lint.py` are not optional for
  governance copy under the documented globs.

## Workflow conventions

- Push to main directly. The repo's CI runs the gates on push; a
  failed gate fails the check.
- Nine python gates run on every push: `spec_check`, `voice_lint`,
  `validate_decisions`, `validate_roles`, `validate_tools`,
  `validate_policies`, `validate_skills`, `validate_dreams`,
  `check_schema_cache_freshness`. Plus pytest.
- Every shipped R-* requirement gets at least one DEC-* file before
  the commit reaches main. `spec_check` flags an orphan R-* unless
  the requirement is listed in
  `decisions/.spec-check-allowlist.yaml` as deferred backfill.
- Dream-job outputs are human-gated. No CI job auto-applies a dream
  candidate. The policy
  `.agents/policies/dream-candidates-require-human-approval.yaml`
  encodes the rule.
- A force-push, history rewrite, or rollback gets an entry in
  `ops/RESET_LEDGER.md` in the same push that performs the rewrite.
- A release gets an entry in `ops/RELEASE_LEDGER.md` with date, SHA,
  title, scope, and proof refs.

## Cross-repo links

- The CDCP charter at `../athena-site/ops/control-plane.md` names
  the six artifact types and the cross-repo contracts.
- The schemas at `../athena-site/ops/schemas/` are the source of
  truth for decision, role, tool, policy, skill, dream-output, and
  artifact shapes. This repo references them by URL and keeps cache
  copies under `ops/schemas-cache/` for offline CI.
- The portfolio manifest at
  `../athena-site/ops/portfolio-manifest.yml` lists every product
  repo and which gates each repo runs.

## Where to look

| If you want to | Read |
|---|---|
| understand the what | `specs/0001-trace-to-eval-harness/requirements.md` |
| understand the why | `decisions/DEC-TTE-*.md` |
| run a regression bundle | `README.md` |
| audit a release | `ops/RELEASE_LEDGER.md` |
| audit a history rewrite | `ops/RESET_LEDGER.md` |
| register a new role, tool, or policy | `.agents/CATALOG.md` |

## Failure modes the agent watches for

- A new R-* requirement without a DEC: `spec_check` fails. Fix by
  adding the DEC file in the same commit.
- A DEC file out of schema shape: `validate_decisions` fails. Fix
  the front-matter against `ops/schemas-cache/decision.schema.json`.
- A role, tool, or policy out of shape: the matching `validate_*`
  script fails. Fix against the cached schema.
- A voice-lint hit in governance copy: rewrite the line.
