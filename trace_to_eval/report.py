from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import write_json


def write_reports(payload: dict[str, Any], json_path: Path) -> Path:
    write_json(json_path, payload)
    markdown_path = json_path.with_suffix(".md")
    markdown_path.write_text(markdown_report(payload), encoding="utf-8")
    return markdown_path


def markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Trace-To-Eval Run Report",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['passed_cases']} passed, {summary['failed_cases']} failed, {summary['total_cases']} total",
        f"- Checks: {summary['passed_checks']} passed, {summary['failed_checks']} failed, {summary['total_checks']} total",
        "",
        "## Suites",
        "",
        "| Suite | Cases | Passed | Failed |",
        "|---|---:|---:|---:|",
    ]
    for suite, counts in sorted(summary["suites"].items()):
        lines.append(
            f"| {suite} | {counts['cases']} | {counts['passed_cases']} | {counts['failed_cases']} |"
        )

    lines.extend(
        [
            "",
            "## Case Results",
            "",
            "| Case | Suite | Trace | Status | Failed checks |",
            "|---|---|---|---|---|",
        ]
    )
    for case in payload["cases"]:
        failed = [check["type"] for check in case["checks"] if not check["passed"]]
        status = "pass" if case["passed"] else "fail"
        failed_text = ", ".join(failed) if failed else ""
        lines.append(
            f"| {case['id']} | {case['suite']} | {case['trace_id']} | {status} | {failed_text} |"
        )

    lines.append("")
    return "\n".join(lines)

