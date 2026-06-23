from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_REPORT = Path("reports/run.json")


def load_report(path: Path) -> dict[str, Any]:
    """Read a run-report JSON file written by the ``run`` command."""
    return json.loads(path.read_text(encoding="utf-8"))


def _observed_snippet(check: dict[str, Any]) -> str:
    """Return a short, single-line description of what the trace produced."""
    observed = check.get("observed")
    if observed is None:
        return check.get("message", "")
    if isinstance(observed, list):
        observed = ", ".join(str(item) for item in observed)
    text = str(observed).replace("\n", " ").strip()
    if len(text) > 70:
        text = text[:67] + "..."
    return text


def format_report(payload: dict[str, Any], source: Path) -> str:
    """Render a committed run report as a ranked, human-readable summary.

    Failing suites are listed first, ranked by failed-case count, so a
    reviewer sees the worst regressions at the top. Each failing case lists
    its failed checks and the offending observed text.
    """
    summary = payload["summary"]
    lines: list[str] = []
    lines.append(f"trace-to-eval report  ({source})")
    lines.append("=" * 56)
    lines.append("")
    lines.append(
        f"cases:  {summary['failed_cases']} failed / {summary['total_cases']} total"
    )
    lines.append(
        f"checks: {summary['failed_checks']} failed / {summary['total_checks']} total"
    )
    lines.append("")

    # Rank suites: most failed cases first, then by name for stability.
    suites = summary.get("suites", {})
    ranked = sorted(
        suites.items(),
        key=lambda kv: (-kv[1].get("failed_cases", 0), kv[0]),
    )
    lines.append("suites (ranked by failed cases)")
    lines.append(f"  {'suite':<22}{'failed':>8}{'cases':>8}")
    for name, counts in ranked:
        lines.append(
            f"  {name:<22}{counts.get('failed_cases', 0):>8}{counts.get('cases', 0):>8}"
        )
    lines.append("")

    # Failing cases with the specific check that broke.
    failing = [case for case in payload.get("cases", []) if not case.get("passed", True)]
    if failing:
        lines.append("failing cases")
        for case in failing:
            lines.append(f"  - {case['id']}  [{case['suite']}]  trace={case['trace_id']}")
            for check in case.get("checks", []):
                if check.get("passed", True):
                    continue
                lines.append(
                    f"      x {check['type']}: {check.get('message', '')}"
                )
                snippet = _observed_snippet(check)
                if snippet and snippet != check.get("message", ""):
                    lines.append(f"        observed: {snippet}")
    else:
        lines.append("all cases passed")
    lines.append("")

    failed_cases = summary["failed_cases"]
    if failed_cases:
        lines.append(
            f"bottom line: {failed_cases} regression(s) are now pinned as "
            "deterministic eval cases."
        )
    else:
        lines.append("bottom line: all pinned eval cases pass.")
    return "\n".join(lines)


def run_show(path: Path | None = None) -> str:
    """Load the committed report (default reports/run.json) and format it."""
    report_path = path or DEFAULT_REPORT
    payload = load_report(report_path)
    return format_report(payload, report_path)
