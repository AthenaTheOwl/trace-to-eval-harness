# Traceability

| Requirement | Owner | Evidence |
|---|---|---|
| R-TTE-001 | owner_role: engineering.implementation | `trace_to_eval/models.py`, `tests/test_runner.py` |
| R-TTE-002 | owner_role: science.eval_curator | `trace_to_eval/ingest.py`, `tests/test_ingest.py` |
| R-TTE-003 | owner_role: science.proof_gate_runner | `trace_to_eval/runner.py`, `examples/eval_cases.yaml` |
| R-TTE-004 | owner_role: science.proof_gate_runner | `trace_to_eval/report.py`, `tests/test_report.py` |
| R-TTE-005 | owner_role: engineering.code_reviewer | `scripts/voice_lint.py`, `scripts/spec_check.py`, `.github/workflows/ci.yml` |

