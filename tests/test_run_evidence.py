from __future__ import annotations

import json
from pathlib import Path

from trace_to_eval.cli import main
from trace_to_eval.run_evidence import build_run_evidence_from_cdcp_events
from trace_to_eval.validation import validate_document

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_EVENT_LOG = ROOT / "tests" / "fixtures" / "cdcp_events" / "event-log"


def test_cdcp_events_build_schema_valid_run_evidence() -> None:
    packet, events_read, line_errors = build_run_evidence_from_cdcp_events(
        FIXTURE_EVENT_LOG
    )

    assert events_read == 2
    assert len(line_errors) == 1
    assert packet["runtime_provider"] == "cdcp-event-log"
    assert packet["run_id"].startswith("cdcp-")
    assert packet["input_refs"][0]["kind"] == "event-log"
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


def test_evidence_from_cdcp_events_cli_writes_valid_packet(tmp_path, capsys) -> None:
    out_file = tmp_path / "packet.json"

    code = main(["evidence", "from-cdcp-events", str(FIXTURE_EVENT_LOG), "--out", str(out_file)])

    captured = capsys.readouterr()
    assert code == 0
    assert "malformed JSONL" in captured.err
    assert "gate result(s)" in captured.out
    assert validate_document("evidence", out_file).passed

    packet = json.loads(out_file.read_text(encoding="utf-8"))
    assert packet["schema_version"] == "1.0.0"
    assert packet["gate_results"][0]["status"] == "failed"


def test_evidence_validate_cli_accepts_fixture(capsys) -> None:
    code = main(["evidence", "validate", "tests/fixtures/valid/run_evidence.json"])

    captured = capsys.readouterr()
    assert code == 0
    assert "run-evidence.schema.json" in captured.out
