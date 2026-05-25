# Traceability

| Requirement | Owner | Evidence |
|---|---|---|
| R-TTE-001 | owner_role: engineering.implementation | `trace_to_eval/models.py`, `tests/test_runner.py` |
| R-TTE-002 | owner_role: science.eval_curator | `trace_to_eval/ingest.py`, `tests/test_ingest.py` |
| R-TTE-003 | owner_role: science.proof_gate_runner | `trace_to_eval/runner.py`, `examples/eval_cases.yaml` |
| R-TTE-004 | owner_role: science.proof_gate_runner | `trace_to_eval/report.py`, `tests/test_report.py` |
| R-TTE-005 | owner_role: engineering.code_reviewer | `scripts/voice_lint.py`, `scripts/spec_check.py`, `.github/workflows/ci.yml` |
| R-TTE-006 | owner_role: science.eval_curator | `trace_to_eval/cdcp_events.py`, `trace_to_eval/cli.py`, `tests/test_cdcp_events.py`, `tests/fixtures/cdcp_events/` |
| R-TTE-SCHEMA-001 | owner_role: engineering.implementation | `schemas/trace.schema.json`, `schemas/eval-case.schema.json`, `schemas/run-report.schema.json` |
| R-TTE-SCHEMA-002 | owner_role: engineering.implementation | `trace_to_eval/cli.py`, `trace_to_eval/validation.py`, `tests/test_validation.py` |
| R-TTE-SCHEMA-003 | owner_role: science.proof_gate_runner | `tests/fixtures/valid/`, `tests/fixtures/invalid/`, `scripts/validate_schemas.py` |
| R-TTE-SCHEMA-004 | owner_role: science.proof_gate_runner | `trace_to_eval/runner.py`, `decisions/DEC-TTE-001-deterministic-checks-before-llm-judges.md`, `decisions/DEC-TTE-005-formal-schemas-before-integrations.md` |
