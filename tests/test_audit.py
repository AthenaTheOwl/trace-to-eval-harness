"""Tests for the trace-to-eval audit log.

Covers ``append_audit_entry`` round-trip, ``summarize`` aggregation,
and the CLI's ``audit summary`` subcommand.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trace_to_eval.audit import (
    append_audit_entry,
    format_summary,
    summarize,
)
from trace_to_eval.cli import main


def test_append_audit_entry_round_trip(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    append_audit_entry(
        "validate-chain",
        ledger_path="ops/event-log/2026-05-29.jsonl",
        run_id="run-test0001",
        result="ok",
        packet_hash="a" * 64,
        log_path=log,
    )
    append_audit_entry(
        "evidence.from-cdcp-events",
        ledger_path="ops/event-log/2026-05-29.jsonl",
        run_id="run-test0002",
        result="ok",
        log_path=log,
    )
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    entries = [json.loads(line) for line in lines]
    assert entries[0]["command"] == "validate-chain"
    assert entries[0]["packet_hash"] == "a" * 64
    assert entries[1]["command"] == "evidence.from-cdcp-events"
    # Each entry carries a timestamp string.
    assert all(isinstance(entry["timestamp"], str) for entry in entries)


def test_summarize_aggregates_by_command_and_ledger(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    for _ in range(3):
        append_audit_entry(
            "validate-chain",
            ledger_path="ops/event-log/A.jsonl",
            run_id="run-a",
            result="ok",
            log_path=log,
        )
    append_audit_entry(
        "validate-chain",
        ledger_path="ops/event-log/B.jsonl",
        run_id="run-b",
        result="ok",
        log_path=log,
    )
    append_audit_entry(
        "evidence.from-cdcp-events",
        ledger_path="ops/event-log/A.jsonl",
        run_id="run-a",
        result="ok",
        log_path=log,
    )
    summary = summarize(log, top_n=5)
    assert summary.total == 5
    assert summary.by_command == {
        "validate-chain": 4,
        "evidence.from-cdcp-events": 1,
    }
    assert summary.by_result == {"ok": 5}
    top_paths = dict(summary.top_ledger_paths)
    assert top_paths["ops/event-log/A.jsonl"] == 4
    assert top_paths["ops/event-log/B.jsonl"] == 1


def test_summarize_empty_log(tmp_path: Path) -> None:
    summary = summarize(tmp_path / "missing.jsonl")
    assert summary.total == 0
    assert summary.first_seen is None


def test_summarize_skips_corrupted_lines(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    append_audit_entry("validate-chain", log_path=log)
    with log.open("a", encoding="utf-8") as handle:
        handle.write("{not-json}\n")
        handle.write("\n")  # empty line
    append_audit_entry("validate-chain", log_path=log)
    summary = summarize(log)
    assert summary.total == 2


def test_summarize_since_filter(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "command": "old",
                        "ledger_path": None,
                        "run_id": None,
                        "result": "ok",
                        "packet_hash": None,
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-06-01T00:00:00+00:00",
                        "command": "new",
                        "ledger_path": None,
                        "run_id": None,
                        "result": "ok",
                        "packet_hash": None,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = summarize(log, since="2026-05-01")
    assert summary.total == 1
    assert summary.by_command == {"new": 1}


def test_format_summary_renders_text(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    append_audit_entry(
        "validate-chain", ledger_path="L1", run_id="R1", log_path=log
    )
    rendered = format_summary(summarize(log))
    assert "1 invocation(s)" in rendered
    assert "validate-chain" in rendered
    assert "L1" in rendered


def test_cli_audit_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "audit.jsonl"
    append_audit_entry("validate-chain", ledger_path="L1", log_path=log)
    append_audit_entry("evidence.from-cdcp-events", ledger_path="L2", log_path=log)
    exit_code = main(["audit", "summary", "--log-path", str(log)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "2 invocation(s)" in captured.out
    assert "validate-chain" in captured.out
    assert "evidence.from-cdcp-events" in captured.out


def test_append_audit_entry_records_failure_fields(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    append_audit_entry(
        "validate-chain",
        ledger_path="ops/event-log/x.jsonl",
        result="fail",
        failing_stage="chain",
        error_message="run record sha does not match ledger payload",
        log_path=log,
    )
    entry = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert entry["result"] == "fail"
    assert entry["failing_stage"] == "chain"
    assert "does not match" in entry["error_message"]


def test_append_audit_entry_truncates_long_error_messages(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    long_message = "x" * 1000
    append_audit_entry(
        "validate-chain",
        result="fail",
        failing_stage="schema",
        error_message=long_message,
        log_path=log,
    )
    entry = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert len(entry["error_message"]) < 300
    assert entry["error_message"].endswith("...")


def test_summarize_includes_by_failing_stage(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    append_audit_entry("validate-chain", result="ok", log_path=log)
    append_audit_entry(
        "validate-chain", result="fail", failing_stage="schema", log_path=log
    )
    append_audit_entry(
        "validate-chain", result="fail", failing_stage="chain", log_path=log
    )
    append_audit_entry(
        "validate-chain", result="fail", failing_stage="schema", log_path=log
    )
    summary = summarize(log_path=log)
    assert summary.by_failing_stage == {"schema": 2, "chain": 1}
    assert summary.by_result == {"ok": 1, "fail": 3}
    rendered = format_summary(summary)
    assert "by failing stage" in rendered
    assert "schema: 2" in rendered
