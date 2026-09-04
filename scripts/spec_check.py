#!/usr/bin/env python3
"""Minimal CDCP-lite gate for spec and decision coverage."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "specs" / "0001-trace-to-eval-harness"
DECISIONS_ROOT = ROOT / "decisions"

REQ_RE = re.compile(r"^###\s+((?:R-TTE-SCHEMA|R-TTE)-\d{3}):", re.M)
OWNER_RE = re.compile(r"\|\s*((?:R-TTE-SCHEMA|R-TTE)-\d{3})\s*\|[^|]*owner_role:\s*([a-z][a-z0-9_]*\.[a-z][a-z0-9_-]*)", re.I)
ID_RE = re.compile(r"\b(?:R-TTE-SCHEMA|R-TTE)-\d{3}\b")


def main() -> int:
    violations: list[str] = []
    req_path = SPEC_ROOT / "requirements.md"
    trace_path = SPEC_ROOT / "traceability.md"
    if not req_path.is_file():
        violations.append("missing specs/0001-trace-to-eval-harness/requirements.md")
    if not trace_path.is_file():
        violations.append("missing specs/0001-trace-to-eval-harness/traceability.md")
    if violations:
        return report(violations)

    req_text = req_path.read_text(encoding="utf-8")
    trace_text = trace_path.read_text(encoding="utf-8")
    req_ids = set(REQ_RE.findall(req_text))
    expected = {f"R-TTE-{index:03d}" for index in range(1, 29)} | {
        f"R-TTE-SCHEMA-{index:03d}" for index in range(1, 7)
    }
    if req_ids != expected:
        violations.append(
            "requirements must define R-TTE-001..028 and "
            f"R-TTE-SCHEMA-001..006; found {sorted(req_ids)}"
        )

    trace_ids = set(ID_RE.findall(trace_text))
    missing_trace = sorted(req_ids - trace_ids)
    if missing_trace:
        violations.append(f"traceability missing {', '.join(missing_trace)}")

    owners = {match.group(1): match.group(2) for match in OWNER_RE.finditer(trace_text)}
    missing_owners = sorted(req_ids - set(owners))
    if missing_owners:
        violations.append(f"traceability rows missing owner_role for {', '.join(missing_owners)}")

    decision_ids: set[str] = set()
    decision_files = sorted(DECISIONS_ROOT.glob("DEC-TTE-*.md"))
    if len(decision_files) < 3:
        violations.append("expected at least three DEC-TTE files")
    for path in decision_files:
        decision_ids.update(ID_RE.findall(path.read_text(encoding="utf-8")))
    missing_decisions = sorted(req_ids - decision_ids)
    if missing_decisions:
        violations.append(f"decisions missing coverage for {', '.join(missing_decisions)}")

    if violations:
        return report(violations)
    print(f"spec_check OK ({len(req_ids)} requirements, owner roles, DEC coverage)")
    return 0


def report(violations: list[str]) -> int:
    print("spec_check: violations found", file=sys.stderr)
    for violation in violations:
        print(f"  - {violation}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
