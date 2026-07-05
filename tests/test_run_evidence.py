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
    assert packet["schema_version"] == "2.1.0"
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


def test_evidence_from_cdcp_events_cli_writes_valid_packet(
    tmp_path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "trace_to_eval.cli.append_audit_entry",
        lambda *_, **__: Path("audit-log.jsonl"),
    )
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
    assert packet["schema_version"] == "2.1.0"
    assert packet["producer_run_id"] == "run-fixture000a"
    assert packet["gate_results"][0]["status"] == "failed"


def test_evidence_validate_cli_accepts_fixture(capsys) -> None:
    code = main(["evidence", "validate", "tests/fixtures/valid/run_evidence.json"])

    captured = capsys.readouterr()
    assert code == 0
    assert "run-evidence.schema.json" in captured.out


def test_all_example_packets_validate() -> None:
    packets = sorted((ROOT / "examples" / "run_evidence").glob("*.packet.json"))

    assert len(packets) >= 8
    for packet in packets:
        result = validate_document("evidence", packet)
        assert result.passed, packet


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


def test_explicit_run_record_cli_override(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI accepts --run-record and writes a valid packet."""
    monkeypatch.setattr(
        "trace_to_eval.cli.append_audit_entry",
        lambda *_, **__: Path("audit-log.jsonl"),
    )
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


# --- Phase 3 (Round 6): repo:// + artifact:// URI handling -------------------

_TEST_SHA = "f2291a447f39e4b4347b2be08fd43491feddfbc1"


def _build_producer_repo_with_uri_record(
    portfolio_root: Path, repo_name: str, run_id: str, outputs: list[dict] | None = None
) -> Path:
    """Build a synthetic producer repo whose Run record carries repo:// URIs.

    Returns the event-log path so the test can invoke the generator.
    """
    producer_root = portfolio_root / repo_name
    (producer_root / "ops" / "event-ledger").mkdir(parents=True)
    (producer_root / "ops" / "run-records").mkdir(parents=True)
    event_log = producer_root / "ops" / "event-ledger" / f"{run_id}.jsonl"
    event_log.write_text(
        f'{{"type":"gate.passed","run_id":"{run_id}","payload":{{}},'
        f'"created_at":"2026-05-29T00:00:00Z"}}\n',
        encoding="utf-8",
    )
    record = {
        "id": run_id,
        "agent_id": "test",
        "runtime": "test",
        "workspace_id": repo_name,
        "started_at": "2026-05-29T00:00:00Z",
        "status": "done",
        "spec_id": "test",
        "sandbox_image_ref": f"repo://{repo_name}@{_TEST_SHA}/",
        "inputs": [
            {"kind": "playbook", "ref": f"repo://{repo_name}@{_TEST_SHA}/playbook.md"}
        ],
        "outputs": outputs if outputs is not None else [],
    }
    (producer_root / "ops" / "run-records" / f"{run_id}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    return event_log


def test_generator_emits_repo_uri_refs_when_sandbox_is_repo_uri(tmp_path: Path) -> None:
    """When Run.sandbox_image_ref is repo://, packet refs are repo:// too."""
    portfolio_root = tmp_path / "portfolio"
    portfolio_root.mkdir()
    event_log = _build_producer_repo_with_uri_record(
        portfolio_root, "demo-repo", "run-uri00000001"
    )

    packet, _, _ = build_run_evidence_from_cdcp_events(
        event_log, portfolio_root=portfolio_root
    )
    assert packet["run_record_ref"] == (
        f"repo://demo-repo@{_TEST_SHA}/ops/run-records/run-uri00000001.json"
    )
    assert packet["event_log_ref"] == (
        f"repo://demo-repo@{_TEST_SHA}/ops/event-ledger/run-uri00000001.jsonl"
    )
    assert packet["sandbox_image_ref"] == f"repo://demo-repo@{_TEST_SHA}/"


def test_generator_resolves_repo_uri_artifact_outputs(tmp_path: Path) -> None:
    """artifact_id repo:// URIs resolve under portfolio_root and produce hashes."""
    portfolio_root = tmp_path / "portfolio"
    portfolio_root.mkdir()
    # Create the brief file the artifact_id points at.
    (portfolio_root / "demo-repo" / "briefs" / "2026-W22").mkdir(parents=True)
    brief_path = portfolio_root / "demo-repo" / "briefs" / "2026-W22" / "brief.md"
    brief_bytes = b"# brief\n"
    brief_path.write_bytes(brief_bytes)
    expected_hash = hashlib.sha256(brief_bytes).hexdigest()

    artifact_uri = f"repo://demo-repo@{_TEST_SHA}/briefs/2026-W22/brief.md"
    opaque_uri = "artifact://demo-repo/watchlist-packet@run-uri00000002"
    event_log = _build_producer_repo_with_uri_record(
        portfolio_root,
        "demo-repo",
        "run-uri00000002",
        outputs=[
            {"artifact_id": artifact_uri, "type": "brief"},
            {"artifact_id": opaque_uri, "type": "watchlist_risk_packet"},
        ],
    )

    packet, _, _ = build_run_evidence_from_cdcp_events(
        event_log, portfolio_root=portfolio_root
    )
    refs = {entry["ref"] for entry in packet["artifact_refs"]}
    assert refs == {artifact_uri, opaque_uri}
    # Only the repo:// URI resolves to a file; artifact:// URIs are opaque.
    hashes = {entry["ref"]: entry["hash"] for entry in packet.get("artifact_hashes", [])}
    assert hashes == {artifact_uri: expected_hash}


def test_generator_falls_back_to_legacy_ref_when_no_repo_uri(tmp_path: Path) -> None:
    """Legacy producers (no repo:// sandbox_image_ref) still get a path-shaped ref."""
    producer_root = tmp_path / "legacy-repo"
    (producer_root / "ops" / "event-ledger").mkdir(parents=True)
    (producer_root / "ops" / "run-records").mkdir(parents=True)
    event_log = producer_root / "ops" / "event-ledger" / "run-legacy0001.jsonl"
    event_log.write_text(
        '{"type":"gate.passed","run_id":"run-legacy0001","payload":{},'
        '"created_at":"2026-05-29T00:00:00Z"}\n',
        encoding="utf-8",
    )
    (producer_root / "ops" / "run-records" / "run-legacy0001.json").write_text(
        json.dumps(
            {
                "id": "run-legacy0001",
                "agent_id": "test",
                "runtime": "test",
                "workspace_id": "legacy-repo",
                "started_at": "2026-05-29T00:00:00Z",
                "status": "done",
                "spec_id": "test",
                # No sandbox_image_ref -> legacy fallback path.
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    packet, _, _ = build_run_evidence_from_cdcp_events(
        event_log, portfolio_root=tmp_path
    )
    # No repo:// scheme; should be a posix path string.
    assert not packet["run_record_ref"].startswith("repo://")
    assert not packet["event_log_ref"].startswith("repo://")
    assert packet["run_record_ref"].endswith("run-legacy0001.json")
    assert packet["event_log_ref"].endswith("run-legacy0001.jsonl")


def test_generator_rejects_malformed_repo_uri_run_record_override(tmp_path: Path) -> None:
    """A malformed repo:// URI passed as --run-record fails with a clear error."""
    event_log = tmp_path / "evt.jsonl"
    event_log.write_text(
        '{"type":"gate.passed","run_id":"run-xxxxxxxxxx","payload":{},'
        '"created_at":"2026-05-29T00:00:00Z"}\n',
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError) as excinfo:
        build_run_evidence_from_cdcp_events(
            event_log,
            # Short sha (not 40 hex chars).
            run_record_path="repo://demo@badsha/ops/run-records/x.json",
        )
    assert "repo://" in str(excinfo.value)
    assert "well-formed" in str(excinfo.value)


def test_generator_rejects_artifact_uri_as_run_record_override(tmp_path: Path) -> None:
    """artifact:// is opaque; it is not a valid run-record path."""
    event_log = tmp_path / "evt.jsonl"
    event_log.write_text(
        '{"type":"gate.passed","run_id":"run-xxxxxxxxxx","payload":{},'
        '"created_at":"2026-05-29T00:00:00Z"}\n',
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError) as excinfo:
        build_run_evidence_from_cdcp_events(
            event_log,
            run_record_path="artifact://demo/opaque-id",
        )
    assert "artifact://" in str(excinfo.value)


def test_portfolio_root_cli_flag_overrides_default(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The --portfolio-root CLI flag threads through to resolve repo:// URIs."""
    monkeypatch.setattr(
        "trace_to_eval.cli.append_audit_entry",
        lambda *_, **__: Path("audit-log.jsonl"),
    )
    portfolio_root = tmp_path / "portfolio"
    portfolio_root.mkdir()
    event_log = _build_producer_repo_with_uri_record(
        portfolio_root, "demo-repo", "run-uri00000003"
    )

    out_file = tmp_path / "packet.json"
    code = main(
        [
            "evidence",
            "from-cdcp-events",
            str(event_log),
            "--out",
            str(out_file),
            "--portfolio-root",
            str(portfolio_root),
        ]
    )
    capsys.readouterr()
    assert code == 0
    packet = json.loads(out_file.read_text(encoding="utf-8"))
    assert packet["run_record_ref"].startswith("repo://demo-repo@")
    assert packet["event_log_ref"].startswith("repo://demo-repo@")
