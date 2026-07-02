from __future__ import annotations

import json

from trace_to_eval.cli import main
from trace_to_eval.report import markdown_report


def test_markdown_case_results_status_column_pins_pass_and_fail() -> None:
    # Golden-master lock on the Case Results Status cell: one passing and one
    # failing case must render as `| pass |` and `| fail |` respectively.
    # Without this, an inverted status still ships a green suite.
    payload = {
        "summary": {
            "passed_cases": 1,
            "failed_cases": 1,
            "total_cases": 2,
            "passed_checks": 1,
            "failed_checks": 1,
            "total_checks": 2,
            "suites": {},
        },
        "cases": [
            {
                "id": "green_case",
                "suite": "demo",
                "trace_id": "t_ok",
                "passed": True,
                "checks": [{"type": "citation_span_present", "passed": True}],
            },
            {
                "id": "red_case",
                "suite": "demo",
                "trace_id": "t_bad",
                "passed": False,
                "checks": [{"type": "citation_span_present", "passed": False}],
            },
        ],
    }

    markdown = markdown_report(payload)

    assert (
        "| green_case | demo | t_ok | pass |  |" in markdown
    )
    assert (
        "| red_case | demo | t_bad | fail | citation_span_present |" in markdown
    )


def test_run_command_writes_json_and_markdown(tmp_path) -> None:
    out = tmp_path / "run.json"

    code = main(
        [
            "run",
            "examples/eval_cases.yaml",
            "--traces",
            "examples/traces",
            "--out",
            str(out),
        ]
    )

    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary"]["failed_cases"] == 3
    markdown = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "# Trace-To-Eval Run Report" in markdown
    assert "bad_citation_regression" in markdown
    # The known-failing regression must render `fail` in its Status cell.
    assert (
        "| bad_citation_regression | citation_integrity | bad_citation | fail |"
        in markdown
    )

