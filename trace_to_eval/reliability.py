"""Aggregate repeated run reports without hiding missing or unstable attempts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .io import write_json
from .validation import validate_document


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _load_report(path: Path) -> dict[str, Any]:
    validation = validate_document("report", path)
    if not validation.passed:
        details = "; ".join(
            f"{issue.location}: {issue.message}" for issue in validation.issues
        )
        raise ValueError(f"invalid run report {path}: {details}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    case_ids = [str(case["id"]) for case in payload["cases"]]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError(f"run report contains duplicate case ids: {path}")
    return payload


def aggregate_reliability(report_paths: Iterable[Path]) -> dict[str, Any]:
    """Compute pass@k and pass^k over ordered report attempts.

    The first supplied report is attempt one. A missing case occupies an attempt
    slot and fails that slot; omissions never improve a reliability score.
    """

    paths = tuple(Path(path) for path in report_paths)
    if not paths:
        raise ValueError("at least one run report is required")
    reports = tuple(_load_report(path) for path in paths)
    case_ids = sorted({str(case["id"]) for report in reports for case in report["cases"]})
    if not case_ids:
        raise ValueError("run reports contain no cases")

    per_report = [
        {str(case["id"]): case for case in report["cases"]}
        for report in reports
    ]
    cases: list[dict[str, Any]] = []
    for case_id in case_ids:
        attempts: list[dict[str, Any]] = []
        suites: set[str] = set()
        statuses: list[bool] = []
        for index, (path, report_cases) in enumerate(zip(paths, per_report), start=1):
            case = report_cases.get(case_id)
            if case is None:
                attempts.append(
                    {
                        "attempt": index,
                        "report": path.as_posix(),
                        "observed": False,
                        "passed": False,
                        "trace_id": None,
                    }
                )
                statuses.append(False)
                continue
            suites.add(str(case["suite"]))
            passed = bool(case["passed"])
            attempts.append(
                {
                    "attempt": index,
                    "report": path.as_posix(),
                    "observed": True,
                    "passed": passed,
                    "trace_id": str(case["trace_id"]),
                }
            )
            statuses.append(passed)
        if len(suites) > 1:
            raise ValueError(
                f"case {case_id!r} changed suites across reports: {sorted(suites)}"
            )
        observed_attempts = sum(bool(attempt["observed"]) for attempt in attempts)
        pass_count = sum(statuses)
        cases.append(
            {
                "id": case_id,
                "suite": next(iter(suites), "missing"),
                "attempts_expected": len(paths),
                "attempts_observed": observed_attempts,
                "pass_count": pass_count,
                "pass_at_1": statuses[0],
                "pass_at_k": pass_count > 0,
                "pass_all_k": observed_attempts == len(paths) and pass_count == len(paths),
                "stable": observed_attempts == len(paths) and len(set(statuses)) == 1,
                "attempts": attempts,
            }
        )

    total_cases = len(cases)
    report_count = len(paths)
    observed_attempts = sum(case["attempts_observed"] for case in cases)
    pass_at_1_cases = sum(bool(case["pass_at_1"]) for case in cases)
    pass_at_k_cases = sum(bool(case["pass_at_k"]) for case in cases)
    pass_all_k_cases = sum(bool(case["pass_all_k"]) for case in cases)
    stable_cases = sum(bool(case["stable"]) for case in cases)
    return {
        "summary": {
            "reports": report_count,
            "cases": total_cases,
            "attempt_slots": total_cases * report_count,
            "observed_attempts": observed_attempts,
            "missing_attempts": total_cases * report_count - observed_attempts,
            "pass_at_1_cases": pass_at_1_cases,
            "pass_at_1_rate": _rate(pass_at_1_cases, total_cases),
            "pass_at_k_cases": pass_at_k_cases,
            "pass_at_k_rate": _rate(pass_at_k_cases, total_cases),
            "pass_all_k_cases": pass_all_k_cases,
            "pass_all_k_rate": _rate(pass_all_k_cases, total_cases),
            "stable_cases": stable_cases,
            "stable_case_rate": _rate(stable_cases, total_cases),
        },
        "reports": [path.as_posix() for path in paths],
        "cases": cases,
    }


def markdown_reliability_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    k = summary["reports"]
    lines = [
        "# Repeated-run reliability report",
        "",
        f"- Reports: {k}",
        f"- Cases: {summary['cases']}",
        f"- Missing attempts: {summary['missing_attempts']}",
        f"- Pass@1: {summary['pass_at_1_rate']:.1%}",
        f"- Pass@{k}: {summary['pass_at_k_rate']:.1%}",
        f"- Pass^{k}: {summary['pass_all_k_rate']:.1%}",
        f"- Stable cases: {summary['stable_case_rate']:.1%}",
        "",
        "| Case | Suite | Passed | Observed | Pass@1 | Pass@k | Pass^k | Stable |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for case in payload["cases"]:
        pass_at_1 = "yes" if case["pass_at_1"] else "no"
        pass_at_k = "yes" if case["pass_at_k"] else "no"
        pass_all_k = "yes" if case["pass_all_k"] else "no"
        stable = "yes" if case["stable"] else "no"
        lines.append(
            f"| {case['id']} | {case['suite']} | "
            f"{case['pass_count']}/{case['attempts_expected']} | "
            f"{case['attempts_observed']}/{case['attempts_expected']} | "
            f"{pass_at_1} | {pass_at_k} | {pass_all_k} | {stable} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_reliability_reports(payload: dict[str, Any], json_path: Path) -> Path:
    write_json(json_path, payload)
    markdown_path = json_path.with_suffix(".md")
    markdown_path.write_text(markdown_reliability_report(payload), encoding="utf-8")
    return markdown_path
