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
python -m trace_to_eval run examples/eval_cases.yaml --traces examples/traces --out reports/run.json
```

The run command writes `reports/run.json` and `reports/run.md`. Add `--fail-on-failure` when a CI gate should exit non-zero on failed cases.

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

## Local Gates

```powershell
python -m pytest
python scripts/voice_lint.py
python scripts/spec_check.py
```

