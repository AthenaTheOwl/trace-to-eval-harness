"""Tests for the run-evidence packet dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trace_to_eval.dashboard import collect, render_markdown, run_dashboard


def _write_packet(
    dir: Path,
    run_id: str,
    repo: str = "ai-field-brief",
    generated_at: str = "2026-06-04T00:00:00Z",
    gates: list[dict] | None = None,
    artifact_count: int = 2,
) -> Path:
    packet = {
        "schema_version": "0.1.0",
        "run_id": run_id,
        "producer_run_id": run_id,
        "runtime_provider": "cdcp-event-log",
        "generated_at": generated_at,
        "event_log_hash": "0" * 64,
        "event_log_ref": f"repo://{repo}@abc/ops/event-log/test.jsonl",
        "run_record_hash": "1" * 64,
        "run_record_ref": f"repo://{repo}@abc/ops/run-records/{run_id}.json",
        "prompt_snapshot_hash": "2" * 64,
        "tool_schemas_snapshot_hash": "3" * 64,
        "sandbox_image_ref": "sha256:abc",
        "artifact_hashes": [
            {"hash": f"{i}" * 64, "ref": f"repo://{repo}@abc/artifact-{i}.txt"}
            for i in range(artifact_count)
        ],
        "artifact_refs": [],
        "artifact_diffs": [],
        "input_refs": [],
        "tool_calls": [],
        "gate_results": gates or [],
        "approval_events": [],
        "policy_decisions": [],
        "mcp_servers": [],
        "trace_refs": [],
        "rollback_refs": [],
        "notes": [],
        "cost_usage": None,
        "model": None,
    }
    path = dir / f"{run_id}.packet.json"
    path.write_text(json.dumps(packet), encoding="utf-8")
    return path


def test_collect_groups_by_producer_repo(tmp_path: Path) -> None:
    _write_packet(tmp_path, "run-a", repo="ai-field-brief", artifact_count=3)
    _write_packet(tmp_path, "run-b", repo="ai-field-brief", artifact_count=1)
    _write_packet(tmp_path, "run-c", repo="procurement-negotiation-lab")

    summaries = collect([tmp_path])

    assert set(summaries) == {"ai-field-brief", "procurement-negotiation-lab"}
    assert summaries["ai-field-brief"].packet_count == 2
    assert summaries["ai-field-brief"].artifact_count == 4
    assert summaries["procurement-negotiation-lab"].packet_count == 1


def test_collect_tracks_latest_by_generated_at(tmp_path: Path) -> None:
    _write_packet(tmp_path, "run-old", generated_at="2026-05-01T00:00:00Z")
    _write_packet(tmp_path, "run-new", generated_at="2026-06-04T00:00:00Z")

    summaries = collect([tmp_path])

    assert summaries["ai-field-brief"].latest_run_id == "run-new"
    assert summaries["ai-field-brief"].latest_generated_at == "2026-06-04T00:00:00Z"


def test_render_markdown_includes_header_and_rows(tmp_path: Path) -> None:
    _write_packet(
        tmp_path,
        "run-a",
        gates=[{"status": "pass"}, {"status": "pass"}, {"status": "fail"}],
    )

    summaries = collect([tmp_path])
    rendered = render_markdown(summaries, [tmp_path])

    assert "Run-evidence packet dashboard" in rendered
    assert "ai-field-brief" in rendered
    assert "Gate-result breakdown" in rendered


def test_run_dashboard_writes_output_when_path_provided(tmp_path: Path) -> None:
    packets_dir = tmp_path / "packets"
    packets_dir.mkdir()
    _write_packet(packets_dir, "run-a")
    out = tmp_path / "dashboard.md"

    run_dashboard([packets_dir], output=out)

    text = out.read_text(encoding="utf-8")
    assert "ai-field-brief" in text


def test_run_dashboard_dedupes_overlapping_paths(tmp_path: Path) -> None:
    repo_dir = tmp_path / "ai-field-brief" / "examples" / "run_evidence"
    repo_dir.mkdir(parents=True)
    _write_packet(repo_dir, "run-a")

    rendered = run_dashboard(
        [repo_dir],
        portfolio_root=tmp_path,
    )

    # Only 1 packet (not 2) — dedupe should kick in.
    assert "| ai-field-brief | 1 |" in rendered
