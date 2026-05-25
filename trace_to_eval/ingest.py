from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import load_trace, write_yaml
from .models import Trace


def _list_expected(expected: dict[str, Any], key: str) -> list[Any]:
    value = expected.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _suite_from_tags(tags: list[str]) -> str:
    lowered = {tag.lower() for tag in tags}
    if lowered & {"bad_citation", "citation", "missing_citation_span"}:
        return "citation_integrity"
    if lowered & {"unsafe_tool", "tool_policy", "tool"}:
        return "tool_policy"
    if lowered & {"missing_refusal", "refusal"}:
        return "refusal_behavior"
    return "generated_regression"


def build_eval_case(trace: Trace, source_path: Path) -> dict[str, Any]:
    expected = trace.expected_behavior
    checks: list[dict[str, Any]] = []

    for text in _list_expected(expected, "required_text"):
        checks.append({"type": "contains_required_text", "value": text})

    for text in _list_expected(expected, "forbidden_text"):
        checks.append({"type": "does_not_contain_text", "value": text})

    for span in _list_expected(expected, "citation_spans"):
        checks.append({"type": "citation_span_present", "value": span})

    tags = {tag.lower() for tag in trace.failure_tags}
    if tags & {"bad_citation", "citation", "missing_citation_span"} and not any(
        check["type"] == "citation_span_present" for check in checks
    ):
        checks.append(
            {
                "type": "citation_span_present",
                "value": "TODO: paste the exact span that must support the cited claim",
            }
        )

    if tags & {"unsafe_tool", "tool_policy", "tool"}:
        allowed = _list_expected(expected, "allowed_tools")
        checks.append({"type": "tool_call_allowed", "allowed_tools": allowed})

    if expected.get("refusal_required") is True or tags & {"missing_refusal", "refusal"}:
        checks.append({"type": "refusal_required"})

    if not checks:
        checks.append(
            {
                "type": "contains_required_text",
                "value": "TODO: replace with text the corrected output must contain",
            }
        )

    return {
        "id": f"{trace.trace_id}_regression",
        "suite": _suite_from_tags(trace.failure_tags),
        "source_trace_id": trace.trace_id,
        "trace_id": trace.trace_id,
        "trace_file": source_path.name,
        "input": trace.input,
        "failure_tags": trace.failure_tags,
        "human_review": {
            "status": "TODO",
            "reviewer": "TODO",
            "notes": "TODO: confirm expected behavior before this case gates a release.",
        },
        "checks": checks,
    }


def ingest_trace(trace_path: Path, out_path: Path) -> dict[str, Any]:
    trace = load_trace(trace_path)
    case = build_eval_case(trace, trace_path)
    payload = {"cases": [case]}
    write_yaml(out_path, payload)
    return payload

