from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from trace_to_eval.cli import main
from trace_to_eval.run_evidence import (
    RunRecordError,
    build_run_evidence_from_cdcp_events,
    canonical_run_record_bytes,
)
from trace_to_eval.validation import validate_document

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_EVENT_LOG_DIR = ROOT / "tests" / "fixtures" / "cdcp_events" / "event-log"
FIXTURE_EVENT_LOG_FILE = FIXTURE_EVENT_LOG_DIR / "2026-05-25.jsonl"
FIXTURE_RUN_RECORD = (
    ROOT / "tests" / "fixtures" / "cdcp_events" / "run-records" / "run-fixture000a.json"
)


def test_cdcp_events_build_schema_valid_run_evidence() -> None:
    packet, events_read, line_errors = build_run_evidence_from_cdcp_events(
        FIXTURE_EVENT_LOG_DIR
    )

    assert events_read == 2
    assert len(line_errors) == 1
    assert packet["runtime_provider"] == "cdcp-event-log"
    # v2: producer identity preserved, no more cdcp-{hash} synthesis.
    assert packet["run_id"] == "run-fixture000a"
    assert packet["producer_run_id"] == "run-fixture000a"
    assert packet["schema_version"] == "2.0.0"
    assert packet["input_refs"][0]["kind"] == "event-log"

    # Run-record + event-log refs and hashes are populated.
    assert packet["run_record_ref"].endswith("run-fixture000a.json")
    assert packet["event_log_ref"].endswith("2026-05-25.jsonl")
    assert len(packet["run_record_hash"]) == 64
    assert len(packet["event_log_hash"]) == 64
    expected_event_hash = hashlib.sha256(FIXTURE_EVENT_LOG_FILE.read_bytes()).hexdigest()
    assert packet["event_log_hash"] == expected_event_hash

    # Replay-equivalence pass-through from Run record.
    assert (
        packet["prompt_snapshot_hash"]
        == "1111111111111111111111111111111111111111111111111111111111111111"
    )
    assert (
        packet["tool_schemas_snapshot_hash"]
        == "2222222222222222222222222222222222222222222222222222222222222222"
    )
    assert "fixture@deadbeef" in packet["sandbox_image_ref"]

    assert packet["gate_results"] == [
        {
            "name": "gate.failed",
            "status": "failed",
            "summary": None,
            "source_event_id": None,
        }
    ]
    assert packet["trace_refs"] == [
        {
            "kind": "trace",
            "uri": "bad_citation.json",
            "hash": None,
            "description": "Trace reference from trace_file",
        },
        {
            "kind": "trace-id",
            "uri": "cdcp_bad_citation",
            "hash": None,
            "description": "Trace id from CDCP event",
        },
        {
            "kind": "trace-id",
            "uri": "ignored_bootstrap",
            "hash": None,
            "description": "Trace id from CDCP event",
        },
    ]


def test_run_record_canonicalization_is_deterministic() -> None:
    record = json.loads(FIXTURE_RUN_RECORD.read_text(encoding="utf-8"))
    bytes_a = canonical_run_record_bytes(record)
    bytes_b = canonical_run_record_bytes(record)
    assert bytes_a == bytes_b
    digest_a = hashlib.sha256(bytes_a).hexdigest()
    digest_b = hashlib.sha256(bytes_b).hexdigest()
    assert digest_a == digest_b

    # Reordering top-level keys must not change the hash.
    reordered = dict(reversed(list(record.items())))
    assert hashlib.sha256(canonical_run_record_bytes(reordered)).hexdigest() == digest_a


def test_event_log_hash_uses_raw_bytes(tmp_path: Path) -> None:
    """event_log_hash hashes raw file bytes, not text-normalized content."""
    # Copy the fixture verbatim and hash directly.
    raw_bytes = FIXTURE_EVENT_LOG_FILE.read_bytes()
    expected = hashlib.sha256(raw_bytes).hexdigest()

    packet, _, _ = build_run_evidence_from_cdcp_events(FIXTURE_EVENT_LOG_DIR)
    assert packet["event_log_hash"] == expected


def test_evidence_from_cdcp_events_cli_writes_valid_packet(tmp_path, capsys) -> None:
    out_file = tmp_path / "packet.json"

    code = main(
        ["evidence", "from-cdcp-events", str(FIXTURE_EVENT_LOG_DIR), "--out", str(out_file)]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "malformed JSONL" in captured.err
    assert "gate result(s)" in captured.out
    assert validate_document("evidence", out_file).passed

    packet = json.loads(out_file.read_text(encoding="utf-8"))
    assert packet["schema_version"] == "2.0.0"
    assert packet["producer_run_id"] == "run-fixture000a"
    assert packet["gate_results"][0]["status"] == "failed"


def test_evidence_validate_cli_accepts_fixture(capsys) -> None:
    code = main(["evidence", "validate", "tests/fixtures/valid/run_evidence.json"])

    captured = capsys.readouterr()
    assert code == 0
    assert "run-evidence.schema.json" in captured.out


def test_missing_run_record_fails_loudly(tmp_path: Path) -> None:
    """If the sibling Run record can't be located, generator must fail loudly."""
    # Build an isolated event-log with no sibling run-records dir.
    event_log_dir = tmp_path / "event-log"
    event_log_dir.mkdir()
    event_log_file = event_log_dir / "lonely.jsonl"
    event_log_file.write_text(
        '{"type":"gate.passed","run_id":"run-orphana000","payload":{},'
        '"created_at":"2026-05-28T00:00:00Z"}\n',
        encoding="utf-8",
    )

    with pytest.raises(RunRecordError) as excinfo:
        build_run_evidence_from_cdcp_events(event_log_dir)
    msg = str(excinfo.value)
    assert "auto-discovery failed" in msg or "Run record" in msg
    assert "--run-record" in msg


def test_run_record_id_mismatch_fails_loudly(tmp_path: Path) -> None:
    """If Run.id != events' run_id, generator must fail (producer bug)."""
    event_log_dir = tmp_path / "event-log"
    event_log_dir.mkdir()
    event_log_file = event_log_dir / "evt.jsonl"
    event_log_file.write_text(
        '{"type":"gate.passed","run_id":"run-events00001","payload":{},'
        '"created_at":"2026-05-28T00:00:00Z"}\n',
        encoding="utf-8",
    )
    # Sibling run record with a DIFFERENT id.
    run_records_dir = tmp_path / "run-records"
    run_records_dir.mkdir()
    mismatched = run_records_dir / "run-events00001.json"
    mismatched.write_text(
        json.dumps(
            {
                "id": "run-recordXX001",  # mismatch
                "agent_id": "test",
                "runtime": "test",
                "workspace_id": "test",
                "started_at": "2026-05-28T00:00:00Z",
                "status": "done",
                "spec_id": "test",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RunRecordError) as excinfo:
        build_run_evidence_from_cdcp_events(event_log_dir)
    msg = str(excinfo.value)
    assert "does not match" in msg
    assert "run-events00001" in msg
    assert "run-recordXX001" in msg


def test_explicit_run_record_override(tmp_path: Path) -> None:
    """The --run-record CLI arg routes through and overrides auto-discovery."""
    # Copy the event log to a location where auto-discovery would fail.
    event_log_dir = tmp_path / "stray-events"
    event_log_dir.mkdir()
    target = event_log_dir / FIXTURE_EVENT_LOG_FILE.name
    shutil.copy2(FIXTURE_EVENT_LOG_FILE, target)
    # No sibling run-records/ -> auto-discovery would fail.
    with pytest.raises(RunRecordError):
        build_run_evidence_from_cdcp_events(event_log_dir)

    # With override, generation succeeds.
    packet, _, _ = build_run_evidence_from_cdcp_events(
        event_log_dir, run_record_path=FIXTURE_RUN_RECORD
    )
    assert packet["producer_run_id"] == "run-fixture000a"


def test_explicit_run_record_cli_override(tmp_path: Path, capsys) -> None:
    """CLI accepts --run-record and writes a valid packet."""
    event_log_dir = tmp_path / "stray-events"
    event_log_dir.mkdir()
    target = event_log_dir / FIXTURE_EVENT_LOG_FILE.name
    shutil.copy2(FIXTURE_EVENT_LOG_FILE, target)

    out_file = tmp_path / "packet.json"
    code = main(
        [
            "evidence",
            "from-cdcp-events",
            str(event_log_dir),
            "--out",
            str(out_file),
            "--run-record",
            str(FIXTURE_RUN_RECORD),
        ]
    )
    capsys.readouterr()
    assert code == 0
    assert validate_document("evidence", out_file).passed
    packet = json.loads(out_file.read_text(encoding="utf-8"))
    assert packet["producer_run_id"] == "run-fixture000a"


def test_run_record_with_artifact_outputs_resolves_hashes(tmp_path: Path) -> None:
    """When Run.outputs[] artifact_ids resolve to files, artifact_hashes are populated."""
    # Build a synthetic producer-repo layout: ops/event-ledger/, ops/run-records/,
    # plus an artifact file at briefs/foo.md.
    producer_root = tmp_path / "producer-repo"
    (producer_root / "ops" / "event-ledger").mkdir(parents=True)
    (producer_root / "ops" / "run-records").mkdir(parents=True)
    (producer_root / "briefs").mkdir(parents=True)
    artifact_path = producer_root / "briefs" / "hello.md"
    artifact_bytes = b"hello world\n"
    artifact_path.write_bytes(artifact_bytes)
    expected_artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()

    event_log = producer_root / "ops" / "event-ledger" / "run-artifact001.jsonl"
    event_log.write_text(
        '{"type":"gate.passed","run_id":"run-artifact001","payload":{},'
        '"created_at":"2026-05-28T00:00:00Z"}\n',
        encoding="utf-8",
    )
    run_record = producer_root / "ops" / "run-records" / "run-artifact001.json"
    run_record.write_text(
        json.dumps(
            {
                "id": "run-artifact001",
                "agent_id": "test",
                "runtime": "test",
                "workspace_id": "test",
                "started_at": "2026-05-28T00:00:00Z",
                "status": "done",
                "spec_id": "test",
                "outputs": [
                    {"artifact_id": "briefs/hello.md", "type": "brief"},
                    {"artifact_id": "briefs/missing.md", "type": "brief"},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    packet, _, _ = build_run_evidence_from_cdcp_events(event_log)
    refs = {entry["ref"] for entry in packet["artifact_refs"]}
    assert refs == {"briefs/hello.md", "briefs/missing.md"}
    hashes = {entry["ref"]: entry["hash"] for entry in packet.get("artifact_hashes", [])}
    # Only the resolvable file is hashed; the missing one is omitted.
    assert hashes == {"briefs/hello.md": expected_artifact_hash}
