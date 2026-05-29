from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cdcp_events import CdcpEvent, JsonLineError, discover_event_log_files, parse_event_logs
from .uri import parse_repo_uri, resolve_ref
from .validation import validate_document

OUTPUT_FILENAME = "run_evidence.json"
DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"
SCHEMA_VERSION = "2.1.0"

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORTFOLIO_ROOT = REPO_ROOT.parent


def default_portfolio_root() -> Path:
    """Resolve the default portfolio root.

    Priority:
      1. ``PORTFOLIO_ROOT`` environment variable (absolute path).
      2. The parent directory of this repo's root.
    """
    override = os.environ.get("PORTFOLIO_ROOT")
    if override:
        return Path(override).resolve()
    return DEFAULT_PORTFOLIO_ROOT


class RunRecordError(ValueError):
    """Raised when the producer Run record cannot be located, read, or matched."""


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


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _sha256_bytes_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_run_record_bytes(record: dict[str, Any]) -> bytes:
    """Canonicalize a Run record for hashing.

    Rule: json.dumps with sort_keys=True, indent=2, ensure_ascii=False,
    then UTF-8 encode. Deterministic for any same-content record.
    """
    return json.dumps(record, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")


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


def _events_run_id(events: list[CdcpEvent]) -> str | None:
    """Return the shared run_id across events, or None if events disagree or are missing it."""
    seen: set[str] = set()
    for event in events:
        run_id = event.payload.get("run_id") or _payload(event.payload).get("run_id")
        if isinstance(run_id, str) and run_id:
            seen.add(run_id)
    if not seen:
        return None
    if len(seen) > 1:
        raise RunRecordError(
            f"event log carries conflicting run_id values: {sorted(seen)} "
            f"(producer bug — every event in a ledger should share one run_id)"
        )
    return next(iter(seen))


def _auto_discover_run_record(event_log_path: Path, run_id: str) -> Path:
    """Default convention: <event_log>.parent.parent / 'run-records' / '<run_id>.json'."""
    return event_log_path.resolve().parent.parent / "run-records" / f"{run_id}.json"


def _load_run_record(
    event_log_path: Path,
    events: list[CdcpEvent],
    run_record_override: Path | str | None,
    portfolio_root: Path,
) -> tuple[dict[str, Any], Path]:
    """Locate and load the producer Run record. Raises RunRecordError on failure.

    The override may be a local filesystem ``Path``, a legacy path
    string, or a ``repo://`` URI string. ``artifact://`` URIs are
    rejected because the Run record must resolve to a JSON file.
    """
    events_run_id = _events_run_id(events)
    if run_record_override is not None:
        # Preserve URI form (avoid Windows-mangled "repo:\..." from Path()).
        if isinstance(run_record_override, Path):
            override_str = run_record_override.as_posix()
        else:
            override_str = str(run_record_override)
        if override_str.startswith("artifact://"):
            raise RunRecordError(
                f"--run-record cannot be an artifact:// URI ({override_str}); "
                f"the Run record must resolve to a JSON file."
            )
        if override_str.startswith("repo://"):
            parsed = parse_repo_uri(override_str)
            if parsed is None:
                raise RunRecordError(
                    f"--run-record {override_str!r} is not a well-formed repo:// URI"
                )
            resolved = resolve_ref(override_str, portfolio_root)
            if resolved is None:
                raise RunRecordError(
                    f"--run-record URI {override_str!r} did not resolve to a path"
                )
            candidate = resolved
        else:
            candidate = Path(override_str)
        if not candidate.is_file():
            raise RunRecordError(
                f"Run record not found at explicit --run-record path: {candidate}. "
                f"Check the path and try again."
            )
    else:
        if events_run_id is None:
            raise RunRecordError(
                f"could not auto-discover Run record from {event_log_path}: "
                f"no run_id field found on any event. "
                f"Pass --run-record <path> explicitly."
            )
        candidate = _auto_discover_run_record(event_log_path, events_run_id)
        if not candidate.is_file():
            raise RunRecordError(
                f"Run record auto-discovery failed: no file at {candidate}. "
                f"Expected convention is <event-log>/../run-records/<run_id>.json. "
                f"Pass --run-record <path> to override."
            )
    try:
        record = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RunRecordError(
            f"Run record at {candidate} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(record, dict):
        raise RunRecordError(
            f"Run record at {candidate} did not parse as a JSON object"
        )
    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id:
        raise RunRecordError(
            f"Run record at {candidate} is missing a non-empty 'id' field"
        )
    if events_run_id is not None and record_id != events_run_id:
        raise RunRecordError(
            f"Run record id {record_id!r} does not match event log run_id "
            f"{events_run_id!r} (producer bug — Run record and ledger must agree)"
        )
    return record, candidate


def _relative_to_repo(path: Path) -> str:
    """Return path relative to REPO_ROOT when possible, else POSIX-form absolute."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        # Path is outside the repo (e.g. a sibling product repo on the same disk).
        try:
            rel = Path(path).resolve().relative_to(REPO_ROOT.parent)
            return ("../" + rel.as_posix()) if not rel.as_posix().startswith("..") else rel.as_posix()
        except ValueError:
            return path.resolve().as_posix()


def _producer_repo_ref(
    record: dict[str, Any],
    file_path: Path,
    rel_path_under_repo: str,
    portfolio_root: Path,
) -> str:
    """Build a portable ref for a producer-side file.

    When the Run record's ``sandbox_image_ref`` is a ``repo://`` URI,
    emit ``repo://<repo>@<sha>/<rel_path_under_repo>`` so the packet
    travels with provenance. Otherwise fall back to a portfolio-relative
    posix path (interop with legacy producers).
    """
    sandbox_ref = record.get("sandbox_image_ref")
    if isinstance(sandbox_ref, str):
        parsed = parse_repo_uri(sandbox_ref)
        if parsed is not None:
            repo, sha, _path = parsed
            return f"repo://{repo}@{sha}/{rel_path_under_repo.lstrip('/')}"
    # Legacy fallback: portfolio-relative posix path.
    try:
        return file_path.resolve().relative_to(portfolio_root).as_posix()
    except ValueError:
        return _relative_to_repo(file_path)


def _resolve_artifact_path(
    repo_root_for_artifact: Path, ref: str, portfolio_root: Path
) -> Path | None:
    """Resolve an artifact ref to a local on-disk path.

    Accepts ``repo://`` URIs (resolved via ``portfolio_root``), legacy
    relative paths (anchored at ``repo_root_for_artifact``), and absolute
    paths. ``artifact://`` URIs return None (not a file path).
    """
    if ref.startswith("repo://"):
        candidate = resolve_ref(ref, portfolio_root)
    elif ref.startswith("artifact://"):
        return None
    else:
        legacy = Path(ref)
        candidate = legacy if legacy.is_absolute() else repo_root_for_artifact / ref
    if candidate is not None and candidate.is_file():
        return candidate
    return None


def _producer_repo_root(run_record_path: Path) -> Path:
    """The producer repo root: ops/run-records/<id>.json -> repo root is .parent.parent.parent."""
    return run_record_path.resolve().parent.parent.parent


def _build_artifact_refs_and_hashes(
    record: dict[str, Any],
    run_record_path: Path,
    portfolio_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    outputs = record.get("outputs")
    if not isinstance(outputs, list):
        return [], []
    producer_root = _producer_repo_root(run_record_path)
    refs: list[dict[str, Any]] = []
    hashes: list[dict[str, Any]] = []
    for output in outputs:
        if not isinstance(output, dict):
            continue
        artifact_id = output.get("artifact_id")
        kind = output.get("type") or "artifact"
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        entry: dict[str, Any] = {
            "kind": str(kind),
            "ref": artifact_id,
            "artifact_id": artifact_id,
        }
        refs.append(entry)
        resolved = _resolve_artifact_path(producer_root, artifact_id, portfolio_root)
        if resolved is not None:
            try:
                digest = _sha256_bytes_hex(resolved.read_bytes())
                hashes.append({"ref": artifact_id, "hash": digest})
            except OSError:
                pass
    return refs, hashes


def build_run_evidence_from_cdcp_events(
    path: Path,
    *,
    run_record_path: Path | str | None = None,
    portfolio_root: Path | None = None,
) -> tuple[dict[str, Any], int, list[JsonLineError]]:
    portfolio_root = (portfolio_root or default_portfolio_root()).resolve()
    files = discover_event_log_files(path)
    events, line_errors = parse_event_logs(path)
    input_refs = [
        {
            "kind": "event-log",
            "uri": file.as_posix(),
            "hash": _sha256_path(file),
            "description": "CDCP event log input",
        }
        for file in files
    ]

    # Pick the canonical source ledger path used for hashing + ref. When the
    # caller pointed at a single file this is unambiguous; when they pointed
    # at a directory we use the first discovered file.
    primary_event_log = files[0] if files else path

    record, located_record_path = _load_run_record(
        primary_event_log, events, run_record_path, portfolio_root
    )
    producer_run_id = record["id"]
    run_record_hash = _sha256_bytes_hex(canonical_run_record_bytes(record))
    event_log_hash = _sha256_bytes_hex(primary_event_log.read_bytes())

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

    artifact_refs, artifact_hashes = _build_artifact_refs_and_hashes(
        record, located_record_path, portfolio_root
    )

    # Producer-side refs: prefer repo:// URI when the Run record carries a
    # repo:// sandbox_image_ref (so the packet is portable across machines).
    run_record_rel = f"ops/run-records/{producer_run_id}.json"
    event_log_rel = f"ops/event-ledger/{primary_event_log.name}"
    run_record_ref_str = _producer_repo_ref(
        record, located_record_path, run_record_rel, portfolio_root
    )
    event_log_ref_str = _producer_repo_ref(
        record, primary_event_log, event_log_rel, portfolio_root
    )

    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": producer_run_id,
        "producer_run_id": producer_run_id,
        "run_record_ref": run_record_ref_str,
        "run_record_hash": run_record_hash,
        "event_log_ref": event_log_ref_str,
        "event_log_hash": event_log_hash,
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
            "Generated from CDCP event log + producer Run record; refs and "
            "hashes preserve provenance.",
        ],
    }

    # Pass-through replay-equivalence fields when present on the Run record.
    prompt_hash = record.get("prompt_snapshot_hash")
    if isinstance(prompt_hash, str) and prompt_hash:
        packet["prompt_snapshot_hash"] = prompt_hash
    tool_hash = record.get("tool_schemas_snapshot_hash")
    if isinstance(tool_hash, str) and tool_hash:
        packet["tool_schemas_snapshot_hash"] = tool_hash
    sandbox_ref = record.get("sandbox_image_ref")
    if isinstance(sandbox_ref, str) and sandbox_ref:
        packet["sandbox_image_ref"] = sandbox_ref

    if artifact_refs:
        packet["artifact_refs"] = artifact_refs
    if artifact_hashes:
        packet["artifact_hashes"] = artifact_hashes

    return packet, len(events), line_errors


def write_run_evidence_from_cdcp_events(
    path: Path,
    out_path: Path,
    *,
    run_record_path: Path | str | None = None,
    portfolio_root: Path | None = None,
) -> RunEvidenceResult:
    packet, events_read, line_errors = build_run_evidence_from_cdcp_events(
        path, run_record_path=run_record_path, portfolio_root=portfolio_root
    )
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
