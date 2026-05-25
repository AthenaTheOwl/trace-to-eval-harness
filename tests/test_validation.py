from __future__ import annotations

from pathlib import Path

import pytest

from trace_to_eval.cli import main
from trace_to_eval.validation import validate_document

ROOT = Path(__file__).resolve().parents[1]

VALID_FIXTURES = [
    ("trace", ROOT / "tests" / "fixtures" / "valid" / "trace.json"),
    ("eval", ROOT / "tests" / "fixtures" / "valid" / "eval_cases.yaml"),
    ("report", ROOT / "tests" / "fixtures" / "valid" / "run_report.json"),
]

INVALID_FIXTURES = [
    ("trace", ROOT / "tests" / "fixtures" / "invalid" / "trace_missing_output.json"),
    ("eval", ROOT / "tests" / "fixtures" / "invalid" / "eval_cases_unknown_check.yaml"),
    ("report", ROOT / "tests" / "fixtures" / "invalid" / "run_report_bad_count.json"),
]


@pytest.mark.parametrize(("kind", "path"), VALID_FIXTURES)
def test_valid_fixtures_match_schema(kind: str, path: Path) -> None:
    result = validate_document(kind, path)

    assert result.passed, result.issues


@pytest.mark.parametrize(("kind", "path"), INVALID_FIXTURES)
def test_invalid_fixtures_fail_schema(kind: str, path: Path) -> None:
    result = validate_document(kind, path)

    assert not result.passed
    assert result.issues


def test_current_examples_match_published_schemas() -> None:
    for path in sorted((ROOT / "examples" / "traces").glob("*.json")):
        assert validate_document("trace", path).passed
    assert validate_document("eval", ROOT / "examples" / "eval_cases.yaml").passed
    assert validate_document("eval", ROOT / "eval_cases" / "generated.yaml").passed
    assert validate_document("report", ROOT / "reports" / "run.json").passed


def test_validate_command_accepts_valid_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["validate", "trace", "tests/fixtures/valid/trace.json"])

    captured = capsys.readouterr()
    assert code == 0
    assert "valid:" in captured.out
    assert "trace.schema.json" in captured.out


def test_validate_command_reports_invalid_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["validate", "eval", "tests/fixtures/invalid/eval_cases_unknown_check.yaml"])

    captured = capsys.readouterr()
    assert code == 1
    assert "invalid:" in captured.err
    assert "/cases/0/checks/0/type" in captured.err
    assert "fuzzy_judge" in captured.err
