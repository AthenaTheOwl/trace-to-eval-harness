# Traceability

| Requirement | Owner | Evidence |
|---|---|---|
| R-TTE-001 | owner_role: engineering.implementation | `trace_to_eval/models.py`, `tests/test_runner.py` |
| R-TTE-002 | owner_role: science.eval_curator | `trace_to_eval/ingest.py`, `tests/test_ingest.py` |
| R-TTE-003 | owner_role: science.proof_gate_runner | `trace_to_eval/runner.py`, `examples/eval_cases.yaml` |
| R-TTE-004 | owner_role: science.proof_gate_runner | `trace_to_eval/report.py`, `tests/test_report.py` |
| R-TTE-005 | owner_role: engineering.code_reviewer | `scripts/voice_lint.py`, `scripts/spec_check.py`, `.github/workflows/ci.yml` |
| R-TTE-006 | owner_role: science.eval_curator | `trace_to_eval/cdcp_events.py`, `trace_to_eval/cli.py`, `tests/test_cdcp_events.py`, `tests/fixtures/cdcp_events/` |
| R-TTE-007 | owner_role: science.eval_curator | `trace_to_eval/run_evidence.py`, `trace_to_eval/cli.py`, `tests/test_run_evidence.py` |
| R-TTE-008 | owner_role: science.eval_curator | `trace_to_eval/run_evidence.py`, `schemas/run-evidence.schema.json`, `tests/test_run_evidence.py` |
| R-TTE-009 | owner_role: science.eval_curator | `trace_to_eval/run_evidence.py`, `trace_to_eval/cli.py`, `tests/test_run_evidence.py` |
| R-TTE-010 | owner_role: science.eval_curator | `trace_to_eval/run_evidence.py`, `schemas/run-evidence.schema.json`, `tests/test_run_evidence.py` |
| R-TTE-011 | owner_role: science.eval_curator | `trace_to_eval/run_evidence.py`, `tests/test_run_evidence.py` |
| R-TTE-012 | owner_role: science.eval_curator | `trace_to_eval/uri.py`, `trace_to_eval/run_evidence.py`, `trace_to_eval/cli.py`, `tests/test_uri.py`, `tests/test_run_evidence.py` |
| R-TTE-013 | owner_role: science.eval_curator | `schemas/run-evidence.schema.json` (v2.1.0), `tests/fixtures/valid/run_evidence.json` |
| R-TTE-014 | owner_role: science.eval_curator | `trace_to_eval/run_evidence.py`, `examples/run_evidence/`, `tests/test_run_evidence.py` |
| R-TTE-015 | owner_role: science.eval_curator | `.github/workflows/run-evidence-gates.yml`, `decisions/DEC-TTE-010-trace-to-eval-harness-ci-enforces-run-evidence-chain.md` |
| R-TTE-016 | owner_role: science.eval_curator | `.github/workflows/run-evidence-gates.yml` (job `consumer-gates`, step `all-example-packets-validate`), `examples/run_evidence/` |
| R-TTE-017 | owner_role: science.eval_curator | `.github/workflows/run-evidence-gates.yml` (job `consumer-gates`, step `uri-resolver-tests`), `tests/test_uri.py`, `tests/test_run_evidence.py` |
| R-TTE-018 | owner_role: science.eval_curator | `.github/workflows/run-evidence-gates.yml`, `decisions/DEC-TTE-010-trace-to-eval-harness-ci-enforces-run-evidence-chain.md` |
| R-TTE-SCHEMA-001 | owner_role: engineering.implementation | `schemas/trace.schema.json`, `schemas/eval-case.schema.json`, `schemas/run-report.schema.json` |
| R-TTE-SCHEMA-002 | owner_role: engineering.implementation | `trace_to_eval/cli.py`, `trace_to_eval/validation.py`, `tests/test_validation.py` |
| R-TTE-SCHEMA-003 | owner_role: science.proof_gate_runner | `tests/fixtures/valid/`, `tests/fixtures/invalid/`, `scripts/validate_schemas.py` |
| R-TTE-SCHEMA-004 | owner_role: science.proof_gate_runner | `trace_to_eval/runner.py`, `decisions/DEC-TTE-001-deterministic-checks-before-llm-judges.md`, `decisions/DEC-TTE-005-formal-schemas-before-integrations.md` |
| R-TTE-SCHEMA-005 | owner_role: engineering.implementation | `schemas/run-evidence.schema.json` (v2), `tests/fixtures/valid/run_evidence.json`, `tests/fixtures/invalid/run_evidence_missing_refs.json` |
