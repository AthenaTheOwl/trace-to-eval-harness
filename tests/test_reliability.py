from __future__ import annotations

import json
from pathlib import Path

import pytest

from trace_to_eval.cli import main
from trace_to_eval.reliability import aggregate_reliability
from trace_to_eval.validation import validate_document


def _write_report(path: Path, outcomes: dict[str, tuple[str, bool]]) -> None:
    cases = []
    for case_id, (suite, passed) in outcomes.items():
        cases.append(
            {
                "id": case_id,
                "suite": suite,
                "trace_id": f"{case_id}-{path.stem}",
                "passed": passed,
                "checks": [
                    {
                        "type": "contains_required_text",
                        "passed": passed,
                        "message": "fixture",
                        "expected": "ok",
                        "observed": "ok" if passed else "bad",
                    }
                ],
            }
        )
    passed_cases = sum(bool(case["passed"]) for case in cases)
    payload = {
        "summary": {
            "total_cases": len(cases),
            "passed_cases": passed_cases,
            "failed_cases": len(cases) - passed_cases,
            "total_checks": len(cases),
            "passed_checks": passed_cases,
            "failed_checks": len(cases) - passed_cases,
            "suites": {},
        },
        "cases": cases,
    }
    for suite in sorted({case["suite"] for case in cases}):
        suite_cases = [case for case in cases if case["suite"] == suite]
        suite_passes = sum(bool(case["passed"]) for case in suite_cases)
        payload["summary"]["suites"][suite] = {
            "cases": len(suite_cases),
            "passed_cases": suite_passes,
            "failed_cases": len(suite_cases) - suite_passes,
        }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_reliability_exposes_intermittent_case(tmp_path) -> None:
    paths = [tmp_path / f"attempt-{index}.json" for index in range(1, 4)]
    _write_report(paths[0], {"steady": ("default", True), "flaky": ("default", True)})
    _write_report(paths[1], {"steady": ("default", True), "flaky": ("default", False)})
    _write_report(paths[2], {"steady": ("default", True), "flaky": ("default", True)})

    payload = aggregate_reliability(paths)

    assert payload["summary"]["pass_at_1_rate"] == 1.0
    assert payload["summary"]["pass_at_k_rate"] == 1.0
    assert payload["summary"]["pass_all_k_rate"] == 0.5
    assert payload["summary"]["stable_case_rate"] == 0.5
    flaky = next(case for case in payload["cases"] if case["id"] == "flaky")
    assert flaky["pass_count"] == 2
    assert flaky["pass_all_k"] is False


def test_missing_case_counts_as_failed_attempt(tmp_path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write_report(first, {"present": ("default", True)})
    _write_report(second, {"other": ("default", True)})

    payload = aggregate_reliability([first, second])

    assert payload["summary"]["missing_attempts"] == 2
    assert payload["summary"]["pass_all_k_rate"] == 0.0


def test_case_cannot_change_suite_between_attempts(tmp_path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write_report(first, {"case": ("default", True)})
    _write_report(second, {"case": ("tool_policy", True)})

    with pytest.raises(ValueError, match="changed suites"):
        aggregate_reliability([first, second])


def test_reliability_cli_writes_schema_valid_report(tmp_path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    output = tmp_path / "reliability.json"
    _write_report(first, {"case": ("default", True)})
    _write_report(second, {"case": ("default", True)})

    code = main(["reliability", str(first), str(second), "--out", str(output)])

    assert code == 0
    assert output.with_suffix(".md").exists()
    assert validate_document("reliability", output).passed
