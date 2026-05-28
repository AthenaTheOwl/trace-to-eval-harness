from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cdcp_events import CdcpEvent, JsonLineError, discover_event_log_files, parse_event_logs
from .validation import validate_document

OUTPUT_FILENAME = "run_evidence.json"
DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"


@dataclass(frozen=True)
class RunEvidenceResult:
    output_path: Path
    events_read: int
    line_errors: list[JsonLineError]
    packet: dict[str, Any]


def _event_id(event: dict[str, Any]) -> str | None:
    value = event.get("event_id") or _payload(event).get("event_id")
    if value is None:
        return None
    return str(value)


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def _event_type(event: dict[str, Any]) -> str:
    value = event.get("type") or _payload(event).get("type") or ""
    return str(value).strip()


def _containers(event: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _payload(event)
    containers: list[dict[str, Any]] = []
    for candidate in (
        event,
        payload,
        payload.get("gate"),
        payload.get("policy"),
        payload.get("approval"),
        payload.get("tool"),
        payload.get("mcp_server"),
        payload.get("diff"),
        payload.get("trace"),
        payload.get("cost_usage"),
    ):
        if isinstance(candidate, dict) and not any(candidate is seen for seen in containers):
            containers.append(candidate)
    return containers


def _first_value(containers: list[dict[str, Any]], keys: tuple[str, ...]) -> Any:
    for container in containers:
        for key in keys:
            if key not in container:
                continue
            value = container[key]
            if value is None or value == "":
                continue
            return value
    return None


def _first_text(containers: list[dict[str, Any]], keys: tuple[str, ...]) -> str | None:
    value = _first_value(containers, keys)
    if value is None or isinstance(value, (dict, list)):
        return None
    return str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _packet_hash(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def _latest_created_at(events: list[CdcpEvent]) -> str:
    values = [
        str(event.payload.get("created_at"))
        for event in events
        if isinstance(event.payload.get("created_at"), str)
    ]
    return max(values) if values else DEFAULT_GENERATED_AT


def _status_from_event_type(event_type: str, explicit: str | None = None) -> str:
    raw = (explicit or "").strip().lower().replace("_", "-")
    if raw in {"passed", "pass", "ok", "success"}:
        return "passed"
    if raw in {"failed", "fail", "error", "failure"}:
        return "failed"
    if raw in {"warn", "warning"}:
        return "warn"
    if raw in {"skipped", "skip"}:
        return "skipped"
    lowered = event_type.lower().replace("_", ".")
    if lowered.endswith((".failed", ".failure")) or ".failed" in lowered:
        return "failed"
    if lowered.endswith((".passed", ".success")) or ".passed" in lowered:
        return "passed"
    if ".warn" in lowered:
        return "warn"
    return "unknown"


def _decision(value: Any, *, policy: bool = False) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if policy:
        if raw in {"allow", "allowed"}:
            return "allow"
        if raw in {"deny", "denied"}:
            return "deny"
        if raw in {"approval_required", "human_approval_required", "requires_approval"}:
            return "human_approval_required"
        return "unknown"
    if raw in {"allow", "allowed"}:
        return "allowed"
    if raw in {"deny", "denied"}:
        return "denied"
    if raw in {"approval_required", "human_approval_required", "requires_approval"}:
        return "approval-required"
    return "unknown"


def _approval_status(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in {"requested", "request", "pending"}:
        return "requested"
    if raw in {"approved", "approve"}:
        return "approved"
    if raw in {"rejected", "reject", "denied"}:
        return "rejected"
    if raw == "expired":
        return "expired"
    return "unknown"


def _change_type(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in {"added", "add", "created"}:
        return "added"
    if raw in {"modified", "modify", "changed", "change"}:
        return "modified"
    if raw in {"deleted", "delete", "removed", "remove"}:
        return "deleted"
    if raw in {"renamed", "rename", "moved", "move"}:
        return "renamed"
    return "unknown"


def _gate_result(event: CdcpEvent) -> dict[str, Any] | None:
    event_type = _event_type(event.payload)
    lowered = event_type.lower()
    containers = _containers(event.payload)
    if "gate" not in lowered and _first_value(containers, ("gate", "gate_name", "check")) is None:
        return None
    name = _first_text(containers, ("name", "gate_name", "check", "script")) or event_type or "gate"
    status = _status_from_event_type(
        event_type,
        _first_text(containers, ("status", "result", "outcome")),
    )
    summary = _first_text(containers, ("summary", "message", "note", "error"))
    return {
        "name": name,
        "status": status,
        "summary": summary,
        "source_event_id": _event_id(event.payload),
    }


def _policy_decision(event: CdcpEvent) -> dict[str, Any] | None:
    event_type = _event_type(event.payload).lower()
    containers = _containers(event.payload)
    decision = _first_text(containers, ("decision", "policy_decision", "verdict"))
    policy_id = _first_text(containers, ("policy_id", "policy"))
    if "policy" not in event_type and decision is None and policy_id is None:
        return None
    subject = _first_text(containers, ("subject", "tool", "server", "capability", "name"))
    if subject is None:
        subject = event_type or "policy"
    return {
        "subject": subject,
        "decision": _decision(decision, policy=True),
        "policy_id": policy_id,
        "reason": _first_text(containers, ("reason", "summary", "message", "note")),
        "source_event_id": _event_id(event.payload),
    }


def _approval_event(event: CdcpEvent) -> dict[str, Any] | None:
    event_type = _event_type(event.payload).lower()
    containers = _containers(event.payload)
    status = _first_text(containers, ("approval_status", "status", "decision"))
    if "approval" not in event_type and status is None:
        return None
    subject = _first_text(containers, ("subject", "tool", "server", "capability", "name"))
    if subject is None:
        subject = event_type or "approval"
    return {
        "subject": subject,
        "status": _approval_status(status),
        "actor": _first_text(containers, ("actor", "reviewer", "approver")),
        "source_event_id": _event_id(event.payload),
    }


def _tool_call(event: CdcpEvent) -> dict[str, Any] | None:
    event_type = _event_type(event.payload).lower()
    containers = _containers(event.payload)
    tool_name = _first_text(containers, ("tool_name", "tool", "name"))
    if "tool" not in event_type and tool_name is None:
        return None
    if tool_name is None:
        tool_name = event_type or "tool"
    return {
        "name": tool_name,
        "server": _first_text(containers, ("server", "mcp_server", "server_name")),
        "decision": _decision(_first_text(containers, ("decision", "verdict", "status"))),
        "source_event_id": _event_id(event.payload),
    }


def _mcp_server(event: CdcpEvent) -> dict[str, Any] | None:
    event_type = _event_type(event.payload).lower()
    containers = _containers(event.payload)
    server_name = _first_text(containers, ("mcp_server", "server", "server_name"))
    if "mcp" not in event_type and server_name is None:
        return None
    if server_name is None:
        server_name = event_type or "mcp-server"
    risk = _first_text(containers, ("risk", "risk_level", "severity"))
    if risk is not None:
        risk = risk.lower()
    return {
        "name": server_name,
        "decision": _decision(_first_text(containers, ("decision", "verdict", "status"))),
        "risk": risk if risk in {"low", "medium", "high", "critical", "unknown"} else "unknown",
        "source_event_id": _event_id(event.payload),
    }


def _artifact_diffs(event: CdcpEvent) -> list[dict[str, Any]]:
    containers = _containers(event.payload)
    source_event_id = _event_id(event.payload)
    diffs: list[dict[str, Any]] = []
    raw_diffs = _first_value(containers, ("artifact_diffs", "diffs", "changed_files", "files"))
    for raw in _as_list(raw_diffs):
        if isinstance(raw, str):
            diffs.append(
                {
                    "path": raw,
                    "change_type": "unknown",
                    "source_event_id": source_event_id,
                }
            )
            continue
        if isinstance(raw, dict):
            path = raw.get("path") or raw.get("file")
            if path:
                diffs.append(
                    {
                        "path": str(path),
                        "change_type": _change_type(raw.get("change_type") or raw.get("status")),
                        "source_event_id": source_event_id,
                    }
                )
    return diffs


def _trace_refs(event: CdcpEvent) -> list[dict[str, Any]]:
    containers = _containers(event.payload)
    refs: list[dict[str, Any]] = []
    for key in ("trace_file", "trace_path", "trace_ref"):
        value = _first_text(containers, (key,))
        if value:
            refs.append(
                {
                    "kind": "trace",
                    "uri": value,
                    "hash": None,
                    "description": f"Trace reference from {key}",
                }
            )
    trace_id = _first_text(containers, ("trace_id", "source_trace_id"))
    if trace_id:
        refs.append(
            {
                "kind": "trace-id",
                "uri": trace_id,
                "hash": None,
                "description": "Trace id from CDCP event",
            }
        )
    return refs


def _rollback_refs(event: CdcpEvent) -> list[dict[str, Any]]:
    containers = _containers(event.payload)
    refs: list[dict[str, Any]] = []
    for raw in _as_list(_first_value(containers, ("rollback_refs", "rollback_ref", "rollback"))):
        if isinstance(raw, str):
            refs.append(
                {
                    "kind": "rollback",
                    "uri": raw,
                    "hash": None,
                    "description": "Rollback reference from CDCP event",
                }
            )
        elif isinstance(raw, dict):
            uri = raw.get("uri") or raw.get("ref") or raw.get("commit")
            if uri:
                refs.append(
                    {
                        "kind": str(raw.get("kind") or "rollback"),
                        "uri": str(uri),
                        "hash": raw.get("hash"),
                        "description": raw.get("description"),
                    }
                )
    return refs


def _cost_usage(events: list[CdcpEvent]) -> dict[str, float] | None:
    totals = {
        "input_tokens": 0.0,
        "output_tokens": 0.0,
        "total_tokens": 0.0,
        "estimated_cost_usd": 0.0,
    }
    found = False
    for event in events:
        cost = _first_value(_containers(event.payload), ("cost_usage", "usage"))
        if not isinstance(cost, dict):
            continue
        for key in totals:
            value = cost.get(key)
            if isinstance(value, (int, float)):
                totals[key] += float(value)
                found = True
    return totals if found else None


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def build_run_evidence_from_cdcp_events(path: Path) -> tuple[dict[str, Any], int, list[JsonLineError]]:
    files = discover_event_log_files(path)
    events, line_errors = parse_event_logs(path)
    input_refs = [
        {
            "kind": "event-log",
            "uri": file.as_posix(),
            "hash": _sha256(file),
            "description": "CDCP event log input",
        }
        for file in files
    ]

    gate_results: list[dict[str, Any]] = []
    policy_decisions: list[dict[str, Any]] = []
    approval_events: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    mcp_servers: list[dict[str, Any]] = []
    artifact_diffs: list[dict[str, Any]] = []
    trace_refs: list[dict[str, Any]] = []
    rollback_refs: list[dict[str, Any]] = []

    for event in events:
        if gate := _gate_result(event):
            gate_results.append(gate)
        if policy := _policy_decision(event):
            policy_decisions.append(policy)
        if approval := _approval_event(event):
            approval_events.append(approval)
        if tool := _tool_call(event):
            tool_calls.append(tool)
        if server := _mcp_server(event):
            mcp_servers.append(server)
        artifact_diffs.extend(_artifact_diffs(event))
        trace_refs.extend(_trace_refs(event))
        rollback_refs.extend(_rollback_refs(event))

    packet = {
        "schema_version": "1.0.0",
        "run_id": f"cdcp-{_packet_hash(files)}",
        "generated_at": _latest_created_at(events),
        "runtime_provider": "cdcp-event-log",
        "model": None,
        "input_refs": input_refs,
        "tool_calls": _dedupe(tool_calls),
        "mcp_servers": _dedupe(mcp_servers),
        "policy_decisions": _dedupe(policy_decisions),
        "approval_events": _dedupe(approval_events),
        "artifact_diffs": _dedupe(artifact_diffs),
        "gate_results": _dedupe(gate_results),
        "cost_usage": _cost_usage(events),
        "trace_refs": _dedupe(trace_refs),
        "rollback_refs": _dedupe(rollback_refs),
        "notes": [
            "Generated from explicit CDCP event-log fields only.",
            "RunState or runtime snapshot data can be attached later as input refs.",
        ],
    }
    return packet, len(events), line_errors


def write_run_evidence_from_cdcp_events(path: Path, out_path: Path) -> RunEvidenceResult:
    packet, events_read, line_errors = build_run_evidence_from_cdcp_events(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation = validate_document("evidence", out_path)
    if not validation.passed:
        messages = "; ".join(
            f"{issue.location}: {issue.message}" for issue in validation.issues
        )
        raise ValueError(f"generated run evidence failed schema validation: {messages}")
    return RunEvidenceResult(
        output_path=out_path,
        events_read=events_read,
        line_errors=line_errors,
        packet=packet,
    )
