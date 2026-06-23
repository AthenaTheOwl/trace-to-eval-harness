from __future__ import annotations

import json
from pathlib import Path

from trace_to_eval.cli import main
from trace_to_eval.show import format_report, run_show


def _write_report(out: Path) -> Path:
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
    return out


def test_show_command_default_report_runs_clean(capsys) -> None:
    # The committed reports/run.json is the default fixture.
    code = main(["show"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "trace-to-eval report" in captured
    assert "suites (ranked by failed cases)" in captured
    assert "bottom line:" in captured


def test_show_explicit_path_lists_failing_cases(tmp_path, capsys) -> None:
    out = _write_report(tmp_path / "run.json")
    code = main(["show", str(out)])
    assert code == 0
    captured = capsys.readouterr().out
    assert "bad_citation_regression" in captured
    assert "3 regression(s)" in captured


def test_show_missing_report_exits_1(tmp_path, capsys) -> None:
    code = main(["show", str(tmp_path / "nope.json")])
    assert code == 1
    err = capsys.readouterr().err
    assert "no report at" in err


def test_format_report_ranks_suites_by_failed_cases() -> None:
    payload = {
        "cases": [],
        "summary": {
            "failed_cases": 5,
            "failed_checks": 5,
            "total_cases": 6,
            "total_checks": 7,
            "suites": {
                "low": {"cases": 1, "failed_cases": 1, "passed_cases": 0},
                "high": {"cases": 4, "failed_cases": 4, "passed_cases": 0},
            },
        },
    }
    rendered = format_report(payload, Path("reports/run.json"))
    assert rendered.index("high") < rendered.index("low")


def test_run_show_returns_string() -> None:
    text = run_show()
    assert isinstance(text, str)
    assert text
