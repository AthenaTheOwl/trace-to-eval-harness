#!/usr/bin/env python3
"""Validate published schemas and the positive and negative fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trace_to_eval.validation import load_schema, schema_kinds, validate_document  # noqa: E402

FIXTURES = [
    ("trace", ROOT / "tests" / "fixtures" / "valid" / "trace.json", True),
    ("eval", ROOT / "tests" / "fixtures" / "valid" / "eval_cases.yaml", True),
    ("report", ROOT / "tests" / "fixtures" / "valid" / "run_report.json", True),
    ("evidence", ROOT / "tests" / "fixtures" / "valid" / "run_evidence.json", True),
    ("reliability", ROOT / "tests" / "fixtures" / "valid" / "reliability_report.json", True),
    ("trace", ROOT / "tests" / "fixtures" / "invalid" / "trace_missing_output.json", False),
    ("eval", ROOT / "tests" / "fixtures" / "invalid" / "eval_cases_unknown_check.yaml", False),
    ("report", ROOT / "tests" / "fixtures" / "invalid" / "run_report_bad_count.json", False),
    ("evidence", ROOT / "tests" / "fixtures" / "invalid" / "run_evidence_missing_refs.json", False),
    ("reliability", ROOT / "tests" / "fixtures" / "invalid" / "reliability_report_bad_rate.json", False),
]


def main() -> int:
    violations: list[str] = []
    for kind in schema_kinds():
        schema = load_schema(kind)
        Draft202012Validator.check_schema(schema)
        if not schema.get("$id"):
            violations.append(f"{kind}: missing $id")
        if not schema.get("version"):
            violations.append(f"{kind}: missing version")

    for kind, path, should_pass in FIXTURES:
        result = validate_document(kind, path)
        rel = path.relative_to(ROOT).as_posix()
        if should_pass and not result.passed:
            messages = "; ".join(f"{issue.location}: {issue.message}" for issue in result.issues)
            violations.append(f"{rel}: expected valid, got {messages}")
        if not should_pass and result.passed:
            violations.append(f"{rel}: expected invalid, got pass")

    if violations:
        print("validate_schemas: violations found", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1

    print(f"validate_schemas OK ({len(schema_kinds())} schema(s), {len(FIXTURES)} fixture(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
