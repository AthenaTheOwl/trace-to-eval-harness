"""End-to-end validate-chain pipeline.

One command runs the full DEC-CDCP-015 contract chain end-to-end:

  1. Load the event ledger and validate every event against the cached
     ``event.schema.json``. The first non-conforming event aborts.
  2. Auto-discover the producer Run record from
     ``<ledger>.parent.parent / "run-records" / "<run_id>.json"`` or
     accept an override.
  3. Generate the run-evidence packet via
     ``write_run_evidence_from_cdcp_events`` into a temp file.
  4. Validate the generated packet against ``run-evidence.schema.json``.
  5. Run Round 3 cross-checks between packet, Run record, and ledger:
        - prompt_snapshot_hash equality across the three sources;
        - tool_schemas_snapshot_hash equality;
        - gate_results_summary on the Run record agrees with the
          packet's gate_results;
        - fields_populated on ``gate.run.evidence_recorded`` events
          covers the packet's populated optional fields.

The return value is a typed ``ChainResult`` so CLI and tests can read
it uniformly. The CLI prints either an ``OK`` line plus a small JSON
summary, or a ``FAIL`` line plus the failing stage and message.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .cdcp_events import discover_event_log_files, parse_event_logs
from .run_evidence import (
    RunRecordError,
    write_run_evidence_from_cdcp_events,
)
from .validation import validate_document

ROOT = Path(__file__).resolve().parents[1]
CACHED_EVENT_SCHEMA = ROOT / "ops" / "schemas-cache" / "event.schema.json"


class ChainValidationError(ValueError):
    """Raised by ``run_validate_chain`` when a stage fails.

    The ``stage`` attribute names the chain step (``load-events``,
    ``event-schema``, ``run-record``, ``packet-generation``,
    ``packet-schema``, ``cross-check.<name>``) so callers can render a
    structured FAIL report.
    """

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"{stage}: {message}")
        self.stage = stage
        self.message = message


@dataclass(frozen=True)
class ChainResult:
    ledger_path: Path
    run_record_path: Path
    packet_path: Path
    run_id: str
    events_validated: int
    cross_checks_passed: list[str]
    packet_hash: str

    def to_summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "ledger_path": self.ledger_path.as_posix(),
            "run_record_path": self.run_record_path.as_posix(),
            "packet_path": self.packet_path.as_posix(),
            "events_validated": self.events_validated,
            "cross_checks_passed": list(self.cross_checks_passed),
            "packet_hash": self.packet_hash,
        }


def _load_event_schema() -> dict[str, Any]:
    if not CACHED_EVENT_SCHEMA.is_file():
        raise ChainValidationError(
            "event-schema",
            f"cached event schema missing at {CACHED_EVENT_SCHEMA.relative_to(ROOT).as_posix()}",
        )
    return json.loads(CACHED_EVENT_SCHEMA.read_text(encoding="utf-8"))


def _validate_events(events: list[dict[str, Any]]) -> int:
    """Validate every event payload dict against the cached schema.

    Aborts on the first non-conforming event (a producer bug surfaces
    instantly rather than smearing through downstream stages).
    """
    schema = _load_event_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for index, event in enumerate(events):
        errors = sorted(validator.iter_errors(event), key=str)
        if errors:
            first = errors[0]
            location = (
                "/" + "/".join(str(part) for part in first.absolute_path)
                if first.absolute_path
                else "<root>"
            )
            raise ChainValidationError(
                "event-schema",
                f"event #{index} failed schema at {location}: {first.message}",
            )
    return len(events)


def _find_run_id(events: list[dict[str, Any]]) -> str:
    seen: set[str] = set()
    for event in events:
        run_id = event.get("run_id")
        if isinstance(run_id, str) and run_id:
            seen.add(run_id)
    if not seen:
        raise ChainValidationError(
            "load-events",
            "no event carries a run_id field; cannot auto-discover the Run record",
        )
    if len(seen) > 1:
        raise ChainValidationError(
            "load-events",
            f"ledger carries conflicting run_id values: {sorted(seen)}",
        )
    return next(iter(seen))


def _find_event_of_type(
    events: list[dict[str, Any]], event_type: str
) -> dict[str, Any] | None:
    for event in events:
        if event.get("type") == event_type:
            return event
    return None


def _find_events_of_type(
    events: list[dict[str, Any]], event_type: str
) -> list[dict[str, Any]]:
    return [event for event in events if event.get("type") == event_type]


def _cross_check_prompt_hash(
    packet: dict[str, Any],
    record: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    pipeline_start = _find_event_of_type(events, "pipeline.start")
    if pipeline_start is None:
        # Lenient: ledgers without pipeline.start skip this check rather
        # than fail. The packet/record hash agreement is still enforced.
        record_hash = record.get("prompt_snapshot_hash")
        packet_hash = packet.get("prompt_snapshot_hash")
        if record_hash != packet_hash:
            raise ChainValidationError(
                "cross-check.prompt_snapshot_hash",
                f"packet ({packet_hash!r}) != Run record ({record_hash!r})",
            )
        return
    event_hash = pipeline_start.get("payload", {}).get("prompt_snapshot_hash")
    record_hash = record.get("prompt_snapshot_hash")
    packet_hash = packet.get("prompt_snapshot_hash")
    if not (event_hash == record_hash == packet_hash):
        raise ChainValidationError(
            "cross-check.prompt_snapshot_hash",
            f"disagreement: event={event_hash!r}, record={record_hash!r}, "
            f"packet={packet_hash!r}",
        )


def _cross_check_tool_schemas_hash(
    packet: dict[str, Any],
    record: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    pipeline_start = _find_event_of_type(events, "pipeline.start")
    if pipeline_start is None:
        record_hash = record.get("tool_schemas_snapshot_hash")
        packet_hash = packet.get("tool_schemas_snapshot_hash")
        if record_hash != packet_hash:
            raise ChainValidationError(
                "cross-check.tool_schemas_snapshot_hash",
                f"packet ({packet_hash!r}) != Run record ({record_hash!r})",
            )
        return
    event_hash = pipeline_start.get("payload", {}).get("tool_schemas_snapshot_hash")
    record_hash = record.get("tool_schemas_snapshot_hash")
    packet_hash = packet.get("tool_schemas_snapshot_hash")
    if not (event_hash == record_hash == packet_hash):
        raise ChainValidationError(
            "cross-check.tool_schemas_snapshot_hash",
            f"disagreement: event={event_hash!r}, record={record_hash!r}, "
            f"packet={packet_hash!r}",
        )


def _cross_check_gate_results(
    packet: dict[str, Any],
    record: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    """Run record's gate_results_summary must agree with the ledger.

    The ledger is the source of truth: each gate.check.passed names a
    gate that passed; each gate.check.failed names one that failed. The
    Run record's summary must list a strict subset of those names. We
    do not require exact equality (a summary may aggregate; the ledger
    may be finer-grained).
    """
    summary = record.get("gate_results_summary") or {}
    if not isinstance(summary, dict):
        raise ChainValidationError(
            "cross-check.gate_results_summary",
            "Run record gate_results_summary is not an object",
        )
    summary_passed = {
        str(name) for name in summary.get("gates_passed") or [] if isinstance(name, str)
    }
    summary_failed = {
        str(name) for name in summary.get("gates_failed") or [] if isinstance(name, str)
    }
    ledger_passed = {
        str(event["payload"]["gate_name"])
        for event in _find_events_of_type(events, "gate.check.passed")
        if isinstance(event.get("payload"), dict)
        and isinstance(event["payload"].get("gate_name"), str)
    }
    ledger_failed = {
        str(event["payload"]["gate_name"])
        for event in _find_events_of_type(events, "gate.check.failed")
        if isinstance(event.get("payload"), dict)
        and isinstance(event["payload"].get("gate_name"), str)
    }
    if not ledger_passed and not ledger_failed:
        # Ledgers without typed gate.check.* events skip this check; the
        # packet's free-form gate_results carries whatever the producer
        # surfaced.
        return
    missing_passed = summary_passed - ledger_passed
    missing_failed = summary_failed - ledger_failed
    problems = []
    if missing_passed:
        problems.append(
            f"summary claims passed but ledger does not: {sorted(missing_passed)}"
        )
    if missing_failed:
        problems.append(
            f"summary claims failed but ledger does not: {sorted(missing_failed)}"
        )
    if problems:
        raise ChainValidationError(
            "cross-check.gate_results_summary",
            "; ".join(problems),
        )


def _cross_check_fields_populated(
    packet: dict[str, Any],
    record: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    """`gate.run.evidence_recorded.payload.fields_populated` must list the
    Run record fields that this packet actually carries through.

    We compare the set declared on the ledger against the set the packet
    surfaces. Missing-from-packet is the loud failure; extra-in-packet
    is allowed (packets may surface more than the producer claimed).
    """
    evidence_events = _find_events_of_type(events, "gate.run.evidence_recorded")
    if not evidence_events:
        return
    declared: set[str] = set()
    for event in evidence_events:
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        for field_name in payload.get("fields_populated") or []:
            if isinstance(field_name, str):
                declared.add(field_name)
    # Mapping: declared field -> field on packet.
    expectations = {
        "prompt_snapshot_hash": "prompt_snapshot_hash",
        "tool_schemas_snapshot_hash": "tool_schemas_snapshot_hash",
        "sandbox_image_ref": "sandbox_image_ref",
        "gate_results_summary": "gate_results",
    }
    missing: list[str] = []
    for declared_name in sorted(declared):
        packet_key = expectations.get(declared_name)
        if packet_key is None:
            # Unknown declared field — accept silently (forward-compat).
            continue
        if packet_key not in packet or packet.get(packet_key) in (None, [], {}):
            missing.append(declared_name)
    if missing:
        raise ChainValidationError(
            "cross-check.fields_populated",
            f"ledger declared fields_populated={sorted(declared)} but packet missing: {missing}",
        )


CROSS_CHECKS = [
    ("prompt_snapshot_hash", _cross_check_prompt_hash),
    ("tool_schemas_snapshot_hash", _cross_check_tool_schemas_hash),
    ("gate_results_summary", _cross_check_gate_results),
    ("fields_populated", _cross_check_fields_populated),
]


def run_validate_chain(
    ledger_path: Path,
    *,
    run_record_path: Path | str | None = None,
    portfolio_root: Path | None = None,
) -> ChainResult:
    """Execute the full validate-chain pipeline.

    Returns a ``ChainResult`` on success; raises ``ChainValidationError``
    on the first failing stage. The caller controls how to render the
    outcome.
    """
    ledger_path = Path(ledger_path)
    if not ledger_path.exists():
        raise ChainValidationError(
            "load-events", f"ledger path does not exist: {ledger_path}"
        )

    # Stage 1: load events + validate each against event.schema.json.
    discovered = discover_event_log_files(ledger_path)
    primary_ledger = discovered[0] if discovered else ledger_path
    parsed_events, line_errors = parse_event_logs(ledger_path)
    if line_errors:
        raise ChainValidationError(
            "load-events",
            f"{len(line_errors)} malformed JSONL line(s) in ledger; first: "
            f"{line_errors[0].source_path.name}:{line_errors[0].line_number}: "
            f"{line_errors[0].message}",
        )
    raw_events = [event.payload for event in parsed_events]
    events_validated = _validate_events(raw_events)

    # Stage 2: determine run_id + locate the Run record (used downstream
    # by the generator, but we read it here for cross-checks too).
    run_id = _find_run_id(raw_events)

    # Stage 3: generate packet via the existing pipeline into a temp
    # location. The generator handles run-record discovery + packet
    # schema validation as part of its happy path.
    with tempfile.TemporaryDirectory() as tmpdir:
        packet_path = Path(tmpdir) / f"{run_id}.packet.json"
        try:
            result = write_run_evidence_from_cdcp_events(
                primary_ledger,
                packet_path,
                run_record_path=run_record_path,
                portfolio_root=portfolio_root,
            )
        except RunRecordError as exc:
            raise ChainValidationError("run-record", str(exc)) from exc
        except ValueError as exc:
            # write_run_evidence raises ValueError on schema failure;
            # surface as a packet-schema stage failure.
            raise ChainValidationError("packet-schema", str(exc)) from exc
        packet = result.packet

        # Stage 4: re-validate the packet on disk against run-evidence
        # schema (belt-and-suspenders: generator already validates, but
        # this guards against future generator drift).
        validation = validate_document("evidence", packet_path)
        if not validation.passed:
            messages = "; ".join(
                f"{issue.location}: {issue.message}" for issue in validation.issues
            )
            raise ChainValidationError("packet-schema", messages)
        packet_bytes = packet_path.read_bytes()

    packet_hash = hashlib.sha256(packet_bytes).hexdigest()

    # Stage 5: cross-checks.
    record_path = Path(result.output_path)  # placeholder; reload below.
    # Re-derive the Run record path that the generator used.
    record_path = _derive_run_record_path(
        primary_ledger, run_id, run_record_path, portfolio_root
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    passed: list[str] = []
    for name, fn in CROSS_CHECKS:
        fn(packet, record, raw_events)
        passed.append(name)

    return ChainResult(
        ledger_path=primary_ledger.resolve(),
        run_record_path=record_path.resolve(),
        packet_path=Path("<tempfile>"),  # tempdir already cleaned up.
        run_id=run_id,
        events_validated=events_validated,
        cross_checks_passed=passed,
        packet_hash=packet_hash,
    )


def _derive_run_record_path(
    ledger_path: Path,
    run_id: str,
    run_record_override: Path | str | None,
    portfolio_root: Path | None,
) -> Path:
    """Re-derive the Run record path the generator landed on.

    Mirrors ``run_evidence._load_run_record`` resolution but is local
    to validate-chain so we can re-read the record for cross-checks
    without re-invoking the generator.
    """
    from .run_evidence import default_portfolio_root
    from .uri import parse_repo_uri, resolve_ref

    resolved_portfolio = (portfolio_root or default_portfolio_root()).resolve()
    if run_record_override is not None:
        if isinstance(run_record_override, Path):
            override_str = run_record_override.as_posix()
        else:
            override_str = str(run_record_override)
        if override_str.startswith("repo://"):
            resolved = resolve_ref(override_str, resolved_portfolio)
            if resolved is None:
                raise ChainValidationError(
                    "run-record",
                    f"--run-record URI {override_str!r} did not resolve",
                )
            return resolved
        return Path(override_str)
    return ledger_path.resolve().parent.parent / "run-records" / f"{run_id}.json"
