# decisions

Specs name the what. Decisions name the why. Every shipped R-*
requirement carries at least one `DEC-*.md` file in this directory
that names the requirement, lists the alternatives, records the
rationale, points at the evidence, and writes down the rollback.

## Format

Each file is a markdown file with YAML front-matter at the top
matching the cross-repo `decision.schema.json` contract from
`https://raw.githubusercontent.com/AthenaTheOwl/athena-site/main/ops/schemas/decision.schema.json`.

The body holds five sections in this order:

1. `## decision` — one or two sentences naming what was chosen.
2. `## alternatives` — other paths considered, each with a label and
   a `rejected_because` reason.
3. `## rationale` — why the chosen path beats the alternatives.
4. `## evidence` — pointers to artifacts, runs, benchmarks, or prior
   decisions consulted.
5. `## rollback` — concrete steps to undo the decision.

## Filename

Filename format: `DEC-<PREFIX>-<NNN>-<kebab-slug>.md`.

The prefix follows the same `R-<PREFIX>-NNN` shape as the requirement
the decision resolves. Example:
`DEC-TTE-001-deterministic-checks-before-llm-judges.md` resolves
`R-TTE-003`.

## Adding a new decision

1. Identify the R-* requirement the decision resolves.
2. Copy an existing DEC file as a starting template.
3. Fill in the front-matter fields per `decision.schema.json`.
4. Write the five body sections.
5. Run `python scripts/validate_decisions.py` and confirm exit 0.
6. Run `python scripts/spec_check.py` and confirm the requirement is
   no longer flagged as orphaned.
