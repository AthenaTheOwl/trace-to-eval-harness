from __future__ import annotations

import json

from trace_to_eval.cli import main


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

