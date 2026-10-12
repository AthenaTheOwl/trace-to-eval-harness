"""Audit tool errors in traces against the success the trace claims.

Each tool error gets one class:

- ``repaired``: a later call to the same tool is not itself an error.
- ``ignored``: no later call to that tool succeeds, and the trace makes no
  success claim.
- ``proceeded_as_success``: no later call to that tool succeeds, and the trace
  claims success anyway.

A separate per-trace flag, ``success_without_effect``, fires when the trace
claims success, made at least one write-tool call, and records an empty
``effects`` list.

Every rule is a listed constant below, and the report names the rule that
fired, so a reviewer can see exactly why a trace was flagged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .io import load_json, write_json
from .models import Trace, tool_call_name

ERROR_STATUSES = ("error", "failed")

SUCCESS_STATUSES = ("success", "succeeded", "completed")

COMPLETION_PHRASES = (
    "task complete",
    "task completed",
    "task is complete",
    "completed successfully",
    "successfully completed",
    "finished successfully",
    "all tests pass",
    "all done",
    "i have completed",
    "has been completed",
)

DEFAULT_WRITE_VERBS = (
    "write",
    "create",
    "update",
    "delete",
    "remove",
    "insert",
    "send",
    "post",
    "put",
    "patch",
    "commit",
    "push",
    "deploy",
    "save",
    "upload",
    "edit",
)

ERROR_CLASSES = ("repaired", "ignored", "proceeded_as_success")

_TOKEN_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


def tool_error_rule(call: Any) -> str | None:
    """Return the rule that marks ``call`` as a tool error, or None."""
    if not isinstance(call, dict):
        return None
    status = call.get("status")
    if isinstance(status, str) and status.strip().lower() in ERROR_STATUSES:
        return f"status={status.strip().lower()}"
    if call.get("is_error") is True:
        return "is_error"
    if call.get("error"):
        return "error_key"
    return None


def _normalize_text(text: str) -> str:
    return " ".join(text.replace("’", "'").lower().split())


def success_claim_rules(trace: Trace) -> list[str]:
    """Return every listed rule under which the trace claims success."""
    rules: list[str] = []
    state = trace.terminal_state
    if isinstance(state, dict):
        status = state.get("status")
        if isinstance(status, str) and status.strip().lower() in SUCCESS_STATUSES:
            rules.append(f"terminal_state.status={status.strip().lower()}")
    output = _normalize_text(trace.output)
    for phrase in COMPLETION_PHRASES:
        if phrase in output:
            rules.append(f"output_phrase:{phrase}")
    return rules


def _name_tokens(name: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(name)}


def is_write_tool(name: str, write_tools: frozenset[str] | None) -> bool:
    """Exact (case-insensitive) match when ``write_tools`` is given, else a verb token match."""
    if write_tools is not None:
        return name.lower() in write_tools
    return bool(_name_tokens(name) & set(DEFAULT_WRITE_VERBS))


def parse_write_tools(value: str | None) -> frozenset[str] | None:
    if value is None:
        return None
    names = frozenset(part.strip().lower() for part in value.split(",") if part.strip())
    if not names:
        raise ValueError("--write-tools needs at least one tool name")
    return names


def audit_trace(
    trace: Trace,
    source: str,
    write_tools: frozenset[str] | None = None,
) -> dict[str, Any]:
    calls = trace.tool_calls
    names = [tool_call_name(call) for call in calls]
    error_rules = [tool_error_rule(call) for call in calls]
    claim_rules = success_claim_rules(trace)
    claimed = bool(claim_rules)

    tool_errors: list[dict[str, Any]] = []
    for index, rule in enumerate(error_rules):
        if rule is None:
            continue
        repaired_by = next(
            (
                later
                for later in range(index + 1, len(calls))
                if names[later] == names[index] and error_rules[later] is None
            ),
            None,
        )
        if repaired_by is not None:
            error_class = "repaired"
        elif claimed:
            error_class = "proceeded_as_success"
        else:
            error_class = "ignored"
        tool_errors.append(
            {
                "index": index,
                "tool": names[index],
                "error_rule": rule,
                "class": error_class,
                "repaired_by": repaired_by,
            }
        )

    write_calls = sum(1 for name in names if is_write_tool(name, write_tools))
    effects_recorded = isinstance(trace.raw.get("effects"), list)
    flags: list[str] = []
    if any(error["class"] == "proceeded_as_success" for error in tool_errors):
        flags.append("proceeded_as_success")
    if claimed and write_calls and effects_recorded and not trace.effects:
        flags.append("success_without_effect")

    return {
        "trace_id": trace.trace_id,
        "source": source,
        "tool_calls": len(calls),
        "success_claim": {"claimed": claimed, "rules": claim_rules},
        "write_calls": write_calls,
        "effects_recorded": effects_recorded,
        "effects": len(trace.effects),
        "tool_errors": tool_errors,
        "flags": flags,
    }


def discover_trace_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            found = sorted(item for item in path.glob("*.json") if item.is_file())
            if not found:
                raise ValueError(f"no trace JSON files in directory {path.as_posix()}")
            files.extend(found)
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(f"no such trace file or directory: {path.as_posix()}")
    if not files:
        raise ValueError("at least one trace file or directory is required")
    return files


def _load_trace(path: Path) -> Trace:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.as_posix()}: trace must be a JSON object")
    try:
        return Trace.from_dict(payload)
    except ValueError as exc:
        raise ValueError(f"{path.as_posix()}: {exc}") from exc


def audit_paths(
    paths: Iterable[Path],
    write_tools: frozenset[str] | None = None,
) -> dict[str, Any]:
    traces = [
        audit_trace(_load_trace(path), path.as_posix(), write_tools)
        for path in discover_trace_files(Path(path) for path in paths)
    ]
    errors = [error for trace in traces for error in trace["tool_errors"]]
    summary = {
        "traces": len(traces),
        "tool_calls": sum(trace["tool_calls"] for trace in traces),
        "tool_errors": len(errors),
        **{name: sum(error["class"] == name for error in errors) for name in ERROR_CLASSES},
        "success_without_effect": sum(
            "success_without_effect" in trace["flags"] for trace in traces
        ),
        "flagged_traces": sum(bool(trace["flags"]) for trace in traces),
    }
    if write_tools is None:
        write_rule = {"source": "default_verbs", "values": list(DEFAULT_WRITE_VERBS)}
    else:
        write_rule = {"source": "option", "values": sorted(write_tools)}
    return {
        "summary": summary,
        "rules": {
            "error_statuses": list(ERROR_STATUSES),
            "success_statuses": list(SUCCESS_STATUSES),
            "completion_phrases": list(COMPLETION_PHRASES),
            "write_tools": write_rule,
        },
        "traces": traces,
    }


def markdown_false_success_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# False-success audit",
        "",
        f"- Traces: {summary['traces']}",
        f"- Tool errors: {summary['tool_errors']}",
        f"- Repaired: {summary['repaired']}",
        f"- Ignored: {summary['ignored']}",
        f"- Proceeded as success: {summary['proceeded_as_success']}",
        f"- Success without effect: {summary['success_without_effect']}",
        f"- Flagged traces: {summary['flagged_traces']}",
        "",
        "| Trace | Success claim | Write calls | Effects | Tool errors | Flags |",
        "|---|---|---:|---:|---|---|",
    ]
    for trace in payload["traces"]:
        claim = ", ".join(trace["success_claim"]["rules"]) or "none"
        effects = str(trace["effects"]) if trace["effects_recorded"] else "not recorded"
        errors = (
            ", ".join(
                f"{error['tool']}#{error['index']} {error['class']} ({error['error_rule']})"
                for error in trace["tool_errors"]
            )
            or "none"
        )
        flags = ", ".join(trace["flags"]) or "none"
        lines.append(
            f"| {trace['trace_id']} | {claim} | {trace['write_calls']} | "
            f"{effects} | {errors} | {flags} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_false_success_reports(payload: dict[str, Any], json_path: Path) -> Path:
    write_json(json_path, payload)
    markdown_path = json_path.with_suffix(".md")
    markdown_path.write_text(markdown_false_success_report(payload), encoding="utf-8")
    return markdown_path


def is_flagged(payload: dict[str, Any]) -> bool:
    return bool(payload["summary"]["flagged_traces"])
