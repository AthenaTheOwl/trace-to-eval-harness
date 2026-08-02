"""Tests for ``evidence validate --strict`` re-hash invariant.

Covers:
- a packet whose stored hashes match the referenced files passes strict
- a packet whose run_record file has been edited fails strict with a
  hash-mismatch failure and exits nonzero
- an artifact ref with a wrong hash fails strict with an artifact-level
  failure
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from trace_to_eval.cli import _strict_rehash_packet, main
from trace_to_eval.run_evidence import canonical_run_record_bytes


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_repo(tmp_path: Path) -> tuple[Path, Path, str, Path, str]:
    """Stage a fake portfolio repo with a run record + event log + one artifact."""
    repo_root = tmp_path / "portfolio"
    repo = repo_root / "fakeproducer"
    rec_dir = repo / "ops" / "run-records"
    rec_dir.mkdir(parents=True)
    rec_path = rec_dir / "run-fixture.json"
    rec_path.write_text('{"id": "run-fixture"}', encoding="utf-8")

    log_dir = repo / "ops" / "event-log"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "fixture.jsonl"
    log_path.write_text('{"event": "x"}\n', encoding="utf-8")

    art_path = repo / "artifact.txt"
    art_path.write_text("hello", encoding="utf-8")

    record_hash = hashlib.sha256(
        canonical_run_record_bytes(json.loads(rec_path.read_text(encoding="utf-8")))
    ).hexdigest()
    assert record_hash != _sha256(rec_path)
    return repo_root, rec_path, record_hash, log_path, _sha256(log_path)


def _packet(repo_root: Path, rec_hash: str, log_hash: str, artifact_hash: str) -> dict:
    sha = "0" * 40
    return {
        "schema_version": "2.1.0",
        "run_id": "run-fixture",
        "producer_run_id": "run-fixture",
        "runtime_provider": "cdcp-event-log",
        "generated_at": "2026-06-05T00:00:00Z",
        "event_log_hash": log_hash,
        "event_log_ref": f"repo://fakeproducer@{sha}/ops/event-log/fixture.jsonl",
        "run_record_hash": rec_hash,
        "run_record_ref": f"repo://fakeproducer@{sha}/ops/run-records/run-fixture.json",
        "prompt_snapshot_hash": "1" * 64,
        "tool_schemas_snapshot_hash": "2" * 64,
        "sandbox_image_ref": "sha256:abc",
        "artifact_hashes": [
            {"hash": artifact_hash, "ref": f"repo://fakeproducer@{sha}/artifact.txt"}
        ],
        "artifact_refs": [],
        "artifact_diffs": [],
        "input_refs": [{"uri": f"repo://fakeproducer@{sha}/artifact.txt", "kind": "doc"}],
        "tool_calls": [],
        "gate_results": [],
        "approval_events": [],
        "policy_decisions": [],
        "mcp_servers": [],
        "trace_refs": [],
        "rollback_refs": [],
        "notes": [],
        "cost_usage": None,
        "model": None,
    }


def test_strict_rehash_passes_when_hashes_match(tmp_path: Path) -> None:
    repo_root, rec, rec_hash, log, log_hash = _make_repo(tmp_path)
    artifact_hash = hashlib.sha256((repo_root / "fakeproducer" / "artifact.txt").read_bytes()).hexdigest()
    packet = _packet(repo_root, rec_hash, log_hash, artifact_hash)
    failures = _strict_rehash_packet(packet, repo_root)
    assert failures == []


def test_strict_rehash_fails_when_run_record_tampered(tmp_path: Path) -> None:
    repo_root, rec, rec_hash, log, log_hash = _make_repo(tmp_path)
    artifact_hash = hashlib.sha256((repo_root / "fakeproducer" / "artifact.txt").read_bytes()).hexdigest()
    packet = _packet(repo_root, rec_hash, log_hash, artifact_hash)
    # Tamper with the run record on disk after the packet was sealed.
    rec.write_text('{"id": "run-fixture", "tampered": true}', encoding="utf-8")
    failures = _strict_rehash_packet(packet, repo_root)
    assert any(k == "run_record" and "hash mismatch" in r for k, r in failures)


def test_strict_rehash_fails_with_wrong_artifact_hash(tmp_path: Path) -> None:
    repo_root, rec, rec_hash, log, log_hash = _make_repo(tmp_path)
    # Use a deliberately wrong artifact hash.
    packet = _packet(repo_root, rec_hash, log_hash, "f" * 64)
    failures = _strict_rehash_packet(packet, repo_root)
    assert any(k == "artifact" for k, _ in failures)


def test_evidence_validate_strict_cli_exits_nonzero_on_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root, rec, rec_hash, log, log_hash = _make_repo(tmp_path)
    artifact_hash = hashlib.sha256((repo_root / "fakeproducer" / "artifact.txt").read_bytes()).hexdigest()
    packet = _packet(repo_root, rec_hash, log_hash, artifact_hash)
    # Write a sealed packet that schema-validates...
    packet_path = tmp_path / "fixture.packet.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    # Then tamper with the run record so strict re-hash fails.
    rec.write_text('{"id": "run-fixture", "tampered": true}', encoding="utf-8")

    # CLI exits 1 in strict mode but 0 without --strict.
    exit_lenient = main(["evidence", "validate", str(packet_path)])
    assert exit_lenient == 0

    exit_strict = main(
        [
            "evidence",
            "validate",
            str(packet_path),
            "--strict",
            "--portfolio-root",
            str(repo_root),
        ]
    )
    assert exit_strict == 1
    captured = capsys.readouterr()
    assert "strict-rehash failure" in captured.err


def test_evidence_validate_strict_uses_default_portfolio_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, rec, rec_hash, log, log_hash = _make_repo(tmp_path)
    artifact_hash = hashlib.sha256(
        (repo_root / "fakeproducer" / "artifact.txt").read_bytes()
    ).hexdigest()
    packet = _packet(repo_root, rec_hash, log_hash, artifact_hash)
    packet_path = tmp_path / "examples" / "run_evidence" / "fixture.packet.json"
    packet_path.parent.mkdir(parents=True)
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    monkeypatch.setattr(
        "trace_to_eval.cli.default_portfolio_root", lambda: repo_root
    )

    exit_code = main(
        ["evidence", "validate", str(packet_path), "--strict"]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "re-hash matches stored hashes" in captured.out
