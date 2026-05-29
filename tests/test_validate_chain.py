"""Tests for ``trace-to-eval validate-chain``.

Covers the end-to-end happy path plus one negative test per stage so a
future bug surfaces against the failing stage name (load-events,
event-schema, run-record, packet-schema, cross-check.<name>).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from trace_to_eval.cli import main
from trace_to_eval.validate_chain import (
    ChainValidationError,
    run_validate_chain,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "validate_chain"
FIXTURE_LEDGER = FIXTURE_DIR / "event-log" / "2026-05-29.jsonl"
FIXTURE_RUN_RECORD = FIXTURE_DIR / "run-records" / "run-chain00000a.json"


def _stage_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Copy the canonical fixture into ``tmp_path`` so mutations stay local."""
    dst_event_log = tmp_path / "event-log" / FIXTURE_LEDGER.name
    dst_run_records = tmp_path / "run-records" / FIXTURE_RUN_RECORD.name
    dst_event_log.parent.mkdir(parents=True, exist_ok=True)
    dst_run_records.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE_LEDGER, dst_event_log)
    shutil.copy(FIXTURE_RUN_RECORD, dst_run_records)
    return dst_event_log, dst_run_records


def test_validate_chain_happy_path(tmp_path: Path) -> None:
    ledger, _ = _stage_fixture(tmp_path)
    result = run_validate_chain(ledger)
    assert result.run_id == "run-chain00000a"
    assert result.events_validated == 5
    assert result.cross_checks_passed == [
        "prompt_snapshot_hash",
        "tool_schemas_snapshot_hash",
        "gate_results_summary",
        "fields_populated",
    ]
    assert len(result.packet_hash) == 64


def test_validate_chain_cli_prints_ok_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger, _ = _stage_fixture(tmp_path)
    exit_code = main(
        [
            "validate-chain",
            str(ledger),
            "--audit-log",
            str(tmp_path / "audit.jsonl"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.startswith("OK validate-chain")
    payload = json.loads(captured.out.split("\n", 1)[1])
    assert payload["run_id"] == "run-chain00000a"
    # Audit log written.
    assert (tmp_path / "audit.jsonl").is_file()


def test_validate_chain_fails_on_malformed_jsonl(tmp_path: Path) -> None:
    ledger, _ = _stage_fixture(tmp_path)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write("{not-json}\n")
    with pytest.raises(ChainValidationError) as exc:
        run_validate_chain(ledger)
    assert exc.value.stage == "load-events"


def test_validate_chain_fails_on_event_schema_violation(tmp_path: Path) -> None:
    ledger, _ = _stage_fixture(tmp_path)
    # Drop the required `created_at` field on the first event so the
    # cached event.schema.json rejects it.
    lines = ledger.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first.pop("created_at")
    lines[0] = json.dumps(first)
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ChainValidationError) as exc:
        run_validate_chain(ledger)
    assert exc.value.stage == "event-schema"


def test_validate_chain_fails_when_run_record_missing(tmp_path: Path) -> None:
    ledger, run_record = _stage_fixture(tmp_path)
    run_record.unlink()
    with pytest.raises(ChainValidationError) as exc:
        run_validate_chain(ledger)
    assert exc.value.stage == "run-record"


def test_validate_chain_fails_on_prompt_hash_disagreement(tmp_path: Path) -> None:
    ledger, run_record = _stage_fixture(tmp_path)
    record = json.loads(run_record.read_text(encoding="utf-8"))
    record["prompt_snapshot_hash"] = (
        "deadbeef" + "0" * 56
    )
    run_record.write_text(json.dumps(record, indent=2), encoding="utf-8")
    with pytest.raises(ChainValidationError) as exc:
        run_validate_chain(ledger)
    assert exc.value.stage == "cross-check.prompt_snapshot_hash"


def test_validate_chain_fails_on_gate_summary_mismatch(tmp_path: Path) -> None:
    ledger, run_record = _stage_fixture(tmp_path)
    record = json.loads(run_record.read_text(encoding="utf-8"))
    record["gate_results_summary"]["gates_passed"] = ["gate_that_never_ran"]
    run_record.write_text(json.dumps(record, indent=2), encoding="utf-8")
    with pytest.raises(ChainValidationError) as exc:
        run_validate_chain(ledger)
    assert exc.value.stage == "cross-check.gate_results_summary"


def test_validate_chain_cli_fail_path_reports_stage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger, run_record = _stage_fixture(tmp_path)
    record = json.loads(run_record.read_text(encoding="utf-8"))
    record["prompt_snapshot_hash"] = "deadbeef" + "0" * 56
    run_record.write_text(json.dumps(record, indent=2), encoding="utf-8")
    exit_code = main(
        [
            "validate-chain",
            str(ledger),
            "--no-audit",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "FAIL: cross-check.prompt_snapshot_hash" in captured.err
