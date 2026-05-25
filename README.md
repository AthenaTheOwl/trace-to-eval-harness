# Trace-To-Eval Harness

## 30-Second Hook

Trace-To-Eval Harness turns a failed AI trace into a checked-in eval case. You feed it JSON from a bad answer, review the generated YAML, then run deterministic checks that produce a JSON and Markdown regression bundle. No model key is needed.

## For Your Role

- Product owner: see which user-facing failure becomes a repeatable case.
- Eval curator: convert trace evidence into review-ready YAML with TODO fields.
- Implementation agent: run checks locally before changing prompts, tools, or retrieval code.
- Review agent: read the report and see which case, suite, and check failed.

## Install And Run

```powershell
python -m pip install -e .[dev]
python -m trace_to_eval ingest examples/traces/bad_citation.json --out eval_cases/generated.yaml
python -m trace_to_eval from-cdcp-events ../portfolio-repo/ops/event-log --out eval_cases/cdcp
python -m trace_to_eval validate trace examples/traces/bad_citation.json
python -m trace_to_eval validate eval examples/eval_cases.yaml
python -m trace_to_eval run examples/eval_cases.yaml --traces examples/traces --out reports/run.json
```

The run command writes `reports/run.json` and `reports/run.md`. Add `--fail-on-failure` when a CI gate should exit non-zero on failed cases.

The CDCP event-log command accepts an event-log file, an event-log
directory, or a repo root with `ops/event-log/*.jsonl`. It writes
`cdcp_event_cases.yaml` with draft cases carrying
`human_review.status: review-needed`.

## What It Catches

- Required text missing from an answer.
- Blocked text that appears in an answer.
- Cited spans that are absent from citation or span payloads.
- Tool calls outside an allowed set.
- Missing refusals for requests that should be refused.

## What It Does Not Catch

- Factual truth beyond the strings and tool rules in the case file.
- Citation quality beyond exact span presence.
- Safety policy gaps that are not encoded as checks.
- LLM-judge scoring. The MVP is deterministic by design.

## Trace Shape

Required fields: `trace_id`, `input`, `output`.

Optional fields: `citations`, `spans`, `tool_calls`, `expected_behavior`, `failure_tags`.

The published schema is `schemas/trace.schema.json` with id
`https://trace-to-eval.dev/schemas/v1/trace.schema.json`.

## Eval Case Shape

```yaml
cases:
  - id: bad_citation_regression
    suite: citation_integrity
    trace_id: bad_citation
    trace_file: bad_citation.json
    checks:
      - type: citation_span_present
        value: "raised the filing count to 42"
```

The published schema is `schemas/eval-case.schema.json` with id
`https://trace-to-eval.dev/schemas/v1/eval-case.schema.json`.

## Run Report Shape

The run command writes JSON matching `schemas/run-report.schema.json`
with id `https://trace-to-eval.dev/schemas/v1/run-report.schema.json`.

Validate any checked-in report with:

```powershell
python -m trace_to_eval validate report reports/run.json
```

## Local Gates

```powershell
python -m pytest
python scripts/voice_lint.py
python scripts/check_no_bom.py
python scripts/spec_check.py
python scripts/validate_schemas.py
python scripts/validate_decisions.py
python scripts/validate_roles.py
python scripts/validate_tools.py
python scripts/validate_policies.py
python scripts/validate_skills.py
python scripts/validate_dreams.py
python scripts/check_schema_cache_freshness.py
```

## Governance

This repo runs under the Cognitive Delivery Control Plane charter at
[`athena-site/ops/control-plane.md`](https://github.com/AthenaTheOwl/athena-site/blob/main/ops/control-plane.md).
The charter names six artifact types (specs, decisions, dreams,
ledgers, schemas, policies) and the cross-repo schemas that gate
each. Local artifacts:

- `specs/0001-trace-to-eval-harness/` names the R-TTE-* requirements.
- `decisions/DEC-TTE-*.md` records each architectural choice.
- `.agents/` holds the six minimum-viable roles, the tool registry,
  the policy set, the state-machines, and the workflows.
- `dreams/` reserves the shape for the weekly offline-cognition pass.
- `ops/RELEASE_LEDGER.md` and `ops/RESET_LEDGER.md` carry the audit
  trail; `ops/event-log/` holds the structured event stream.

## License

MIT. See [LICENSE](LICENSE).
