from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import write_yaml
from .validation import validate_document

OUTPUT_FILENAME = "cdcp_event_cases.yaml"

ALLOWED_SUITES = {
    "citation_integrity",
    "tool_policy",
    "refusal_behavior",
    "generated_regression",
    "all_checks",
    "default",
}
KNOWN_FAILURE_TAGS = {
    "bad_citation",
    "citation",
    "missing_citation_span",
    "unsafe_tool",
    "tool_policy",
    "tool",
    "missing_refusal",
    "refusal",
}
ALLOWED_CHECK_TYPES = {
    "contains_required_text",
    "does_not_contain_text",
    "citation_span_present",
    "tool_call_allowed",
    "refusal_required",
}
TEXT_CHECK_TYPES = {
    "contains_required_text",
    "does_not_contain_text",
    "citation_span_present",
}
GATE_EVENT_TYPES = {
    "gate.failed",
    "gate.failure",
    "proof.gate.failed",
    "proof.gate.failure",
    "proof_gate.failed",
    "proof_gate.failure",
    "cdcp.gate.failed",
    "ci.gate.failed",
}
REVIEW_EVENT_PREFIXES = (
    "review.finding",
    "code.review.finding",
    "code_review.finding",
)
INCIDENT_EVENT_TYPES = {
    "incident.opened",
    "incident.created",
    "incident.detected",
    "incident.regression",
}
INCIDENT_CLOSED_SUFFIXES = (".closed", ".resolved", ".mitigated")


@dataclass(frozen=True)
class JsonLineError:
    source_path: Path
    line_number: int
    message: str
    raw: str


@dataclass(frozen=True)
class CdcpEvent:
    source_path: Path
    line_number: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class CdcpImportResult:
    output_path: Path | None
    events_read: int
    ignored_events: int
    line_errors: list[JsonLineError]
    cases: list[dict[str, Any]]

    @property
    def case_count(self) -> int:
        return len(self.cases)


def discover_event_log_files(path: Path) -> list[Path]:
    source = path.resolve()
    if source.is_file():
        return [source]
    if not source.exists():
        raise FileNotFoundError(f"CDCP event-log path does not exist: {path}")
    event_log_dir = source / "ops" / "event-log"
    root = event_log_dir if event_log_dir.is_dir() else source
    files = sorted(root.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"no CDCP JSONL event logs found under {path}")
    return files


def parse_event_logs(path: Path) -> tuple[list[CdcpEvent], list[JsonLineError]]:
    events: list[CdcpEvent] = []
    errors: list[JsonLineError] = []
    for source_path in discover_event_log_files(path):
        lines = source_path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(
                    JsonLineError(
                        source_path=source_path,
                        line_number=line_number,
                        message=f"invalid JSON: {exc.msg}",
                        raw=line.rstrip(),
                    )
                )
                continue
            if not isinstance(payload, dict):
                errors.append(
                    JsonLineError(
                        source_path=source_path,
                        line_number=line_number,
                        message="line is not a JSON object",
                        raw=line.rstrip(),
                    )
                )
                continue
            events.append(
                CdcpEvent(
                    source_path=source_path,
                    line_number=line_number,
                    payload=payload,
                )
            )
    return events, errors


def _payload_dict(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    if isinstance(payload, dict):
        return payload
    return {}


def _containers(event: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _payload_dict(event)
    containers: list[dict[str, Any]] = []
    for candidate in (
        payload,
        payload.get("trace"),
        payload.get("finding"),
        payload.get("gate"),
        payload.get("incident"),
        payload.get("case"),
        event,
    ):
        if isinstance(candidate, dict) and not any(candidate is seen for seen in containers):
            containers.append(candidate)
    return containers


def _event_type(event: dict[str, Any]) -> str:
    raw = event.get("type") or _payload_dict(event).get("type") or ""
    return str(raw).strip().lower()


def _normalized_event_type(event: dict[str, Any]) -> str:
    return _event_type(event).replace("_", ".")


def is_candidate_event(event: dict[str, Any]) -> bool:
    event_type = _normalized_event_type(event)
    if event_type in GATE_EVENT_TYPES:
        return True
    if "gate" in event_type and event_type.endswith((".failed", ".failure")):
        return True
    if any(event_type.startswith(prefix) for prefix in REVIEW_EVENT_PREFIXES):
        return True
    if event_type in INCIDENT_EVENT_TYPES:
        return True
    if event_type.startswith("incident.") and not event_type.endswith(INCIDENT_CLOSED_SUFFIXES):
        return True
    return False


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


def _failure_tags(containers: list[dict[str, Any]]) -> list[str]:
    tags: list[str] = []
    for key in ("failure_tags", "failure_tag"):
        for raw_tag in _as_list(_first_value(containers, (key,))):
            tag = str(raw_tag)
            if tag in KNOWN_FAILURE_TAGS and tag not in tags:
                tags.append(tag)
        if tags:
            return tags
    return tags


def _suite_from_tags(tags: list[str]) -> str:
    lowered = {tag.lower() for tag in tags}
    if lowered & {"bad_citation", "citation", "missing_citation_span"}:
        return "citation_integrity"
    if lowered & {"unsafe_tool", "tool_policy", "tool"}:
        return "tool_policy"
    if lowered & {"missing_refusal", "refusal"}:
        return "refusal_behavior"
    return "generated_regression"


def _suite(containers: list[dict[str, Any]], tags: list[str]) -> str:
    suite = _first_text(containers, ("suite", "eval_suite"))
    if suite in ALLOWED_SUITES:
        return suite
    return _suite_from_tags(tags)


def _normalize_check(raw_check: Any) -> dict[str, Any] | None:
    if not isinstance(raw_check, dict):
        return None
    check_type = str(raw_check.get("type", ""))
    if check_type not in ALLOWED_CHECK_TYPES:
        return None

    check: dict[str, Any] = {"type": check_type}
    if isinstance(raw_check.get("case_insensitive"), bool):
        check["case_insensitive"] = raw_check["case_insensitive"]

    if check_type in TEXT_CHECK_TYPES:
        if "value" in raw_check:
            check["value"] = raw_check["value"]
            return check
        values = raw_check.get("values")
        if isinstance(values, list) and values:
            check["values"] = values
            return check
        return None

    if check_type == "tool_call_allowed":
        check["allowed_tools"] = [
            str(tool) for tool in _as_list(raw_check.get("allowed_tools"))
        ]
        return check

    markers = raw_check.get("markers")
    if isinstance(markers, list) and markers:
        check["markers"] = [str(marker) for marker in markers]
    return check


def _checks_from_explicit_payload(containers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = _first_value(containers, ("checks",))
    if isinstance(checks, list):
        return [check for raw in checks if (check := _normalize_check(raw)) is not None]
    check = _normalize_check(_first_value(containers, ("check",)))
    return [check] if check is not None else []


def _checks_from_expected_behavior(containers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected = _first_value(containers, ("expected_behavior",))
    if not isinstance(expected, dict):
        return []

    checks: list[dict[str, Any]] = []
    for value in _as_list(expected.get("required_text")):
        checks.append({"type": "contains_required_text", "value": value})
    for value in _as_list(expected.get("forbidden_text")):
        checks.append({"type": "does_not_contain_text", "value": value})
    for value in _as_list(expected.get("citation_spans")):
        checks.append({"type": "citation_span_present", "value": value})
    allowed_tools = expected.get("allowed_tools")
    if allowed_tools is not None:
        checks.append(
            {
                "type": "tool_call_allowed",
                "allowed_tools": [str(tool) for tool in _as_list(allowed_tools)],
            }
        )
    if expected.get("refusal_required") is True:
        checks.append({"type": "refusal_required"})
    return [check for check in checks if _normalize_check(check) is not None]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "cdcp_event"


def _case_id(containers: list[dict[str, Any]], trace_id: str, event_type: str) -> str:
    explicit = _first_text(containers, ("candidate_id", "eval_case_id"))
    if explicit is not None:
        return _slug(explicit)
    return f"{_slug(trace_id)}_{_slug(event_type)}_draft"


def case_from_cdcp_event(event: CdcpEvent) -> dict[str, Any] | None:
    if not is_candidate_event(event.payload):
        return None

    containers = _containers(event.payload)
    trace_id = _first_text(containers, ("trace_id", "source_trace_id"))
    if trace_id is None:
        return None

    tags = _failure_tags(containers)
    event_type = _event_type(event.payload) or "cdcp.event"
    checks = _checks_from_explicit_payload(containers) or _checks_from_expected_behavior(
        containers
    )
    if not checks:
        checks = [
            {
                "type": "contains_required_text",
                "value": "TODO: replace with text the corrected output must contain",
            }
        ]

    case: dict[str, Any] = {
        "id": _case_id(containers, trace_id, event_type),
        "suite": _suite(containers, tags),
        "source_trace_id": trace_id,
        "trace_id": trace_id,
        "human_review": {
            "status": "review-needed",
            "reviewer": "TODO",
            "notes": (
                f"Draft from CDCP event log {event.source_path.name}:{event.line_number}; "
                "confirm before promotion."
            ),
        },
        "checks": checks,
    }

    trace_file = _first_text(containers, ("trace_file", "trace_path"))
    if trace_file is not None:
        case["trace_file"] = trace_file
    input_value = _first_value(containers, ("input", "prompt", "request"))
    if input_value is not None:
        case["input"] = input_value
    if tags:
        case["failure_tags"] = tags

    return case


def cases_from_cdcp_events(events: list[CdcpEvent]) -> tuple[list[dict[str, Any]], int]:
    cases: list[dict[str, Any]] = []
    ignored = 0
    seen_ids: set[str] = set()
    for event in events:
        case = case_from_cdcp_event(event)
        if case is None:
            ignored += 1
            continue
        base_id = str(case["id"])
        case_id = base_id
        if case_id in seen_ids:
            case_id = f"{base_id}_line_{event.line_number}"
            counter = 2
            while case_id in seen_ids:
                case_id = f"{base_id}_line_{event.line_number}_{counter}"
                counter += 1
            case["id"] = case_id
        seen_ids.add(case_id)
        cases.append(case)
    return cases, ignored


def import_cdcp_events(path: Path, out_dir: Path) -> CdcpImportResult:
    events, line_errors = parse_event_logs(path)
    cases, ignored_events = cases_from_cdcp_events(events)
    if not cases:
        return CdcpImportResult(
            output_path=None,
            events_read=len(events),
            ignored_events=ignored_events,
            line_errors=line_errors,
            cases=[],
        )

    output_path = out_dir / OUTPUT_FILENAME
    write_yaml(output_path, {"cases": cases})
    validation = validate_document("eval", output_path)
    if not validation.passed:
        messages = "; ".join(
            f"{issue.location}: {issue.message}" for issue in validation.issues
        )
        raise ValueError(
            f"generated CDCP event cases failed schema validation: {messages}"
        )
    return CdcpImportResult(
        output_path=output_path,
        events_read=len(events),
        ignored_events=ignored_events,
        line_errors=line_errors,
        cases=cases,
    )
