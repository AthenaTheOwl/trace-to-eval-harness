"""Tests for the run-bundle primitives + CLI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from trace_to_eval.cli import _parse_artifact_spec, main
from trace_to_eval.run_bundle import (
    BundleComparison,
    canonical_bundle_id,
    compare_bundles,
    create_bundle,
    fingerprint_prompts_and_tools,
    read_bundle,
    validate_bundle,
    write_bundle,
)


def _hash_str(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---- Pure-data helpers ----------------------------------------------------


def test_canonical_bundle_id_is_deterministic() -> None:
    a = canonical_bundle_id("run-1", "local_baseline", "f" * 64)
    b = canonical_bundle_id("run-1", "local_baseline", "f" * 64)
    assert a == b
    assert a.startswith("bundle-")


def test_canonical_bundle_id_distinguishes_adapter() -> None:
    a = canonical_bundle_id("run-1", "local_baseline", "f" * 64)
    b = canonical_bundle_id("run-1", "openai_agents", "f" * 64)
    assert a != b


def test_fingerprint_is_order_insensitive_for_dict_keys() -> None:
    a = fingerprint_prompts_and_tools(["p1"], [{"name": "x", "params": {"a": 1, "b": 2}}])
    b = fingerprint_prompts_and_tools(["p1"], [{"params": {"b": 2, "a": 1}, "name": "x"}])
    assert a == b


def test_fingerprint_changes_with_prompt() -> None:
    a = fingerprint_prompts_and_tools(["p1"], [])
    b = fingerprint_prompts_and_tools(["p1 different"], [])
    assert a != b


# ---- create_bundle --------------------------------------------------------


def test_create_bundle_includes_required_fields() -> None:
    bundle = create_bundle(
        run_id="run-1",
        runtime_adapter="local_baseline",
        generated_at="2026-06-17T12:00:00Z",
        run_record_ref="ops/run-records/run-1.json",
        run_record_hash="a" * 64,
        event_ledger_ref="ops/event-log/run-1.jsonl",
        event_ledger_hash="b" * 64,
        model_tools_fingerprint="c" * 64,
        artifacts=[{"ref": "out.md", "hash": "d" * 64, "kind": "brief"}],
    )
    assert bundle["schema_version"] == "1.0.0"
    assert bundle["run_id"] == "run-1"
    assert bundle["runtime_adapter"] == "local_baseline"
    assert bundle["replay_status"] == "not_attempted"
    assert bundle["artifacts"][0]["kind"] == "brief"


def test_create_bundle_omits_optional_when_unset() -> None:
    bundle = create_bundle(
        run_id="run-2",
        runtime_adapter="local_baseline",
        generated_at="2026-06-17T12:00:00Z",
        run_record_ref="ops/run-records/run-2.json",
        run_record_hash="a" * 64,
        event_ledger_ref="ops/event-log/run-2.jsonl",
        event_ledger_hash="b" * 64,
        model_tools_fingerprint="c" * 64,
    )
    assert "trace_ref" not in bundle
    assert "sandbox_manifest_ref" not in bundle
    assert "adapter_version" not in bundle


# ---- validate_bundle ------------------------------------------------------


def test_validate_bundle_accepts_well_formed(tmp_path: Path) -> None:
    bundle = create_bundle(
        run_id="run-1",
        runtime_adapter="local_baseline",
        generated_at="2026-06-17T12:00:00Z",
        run_record_ref="ops/run-records/run-1.json",
        run_record_hash="a" * 64,
        event_ledger_ref="ops/event-log/run-1.jsonl",
        event_ledger_hash="b" * 64,
        model_tools_fingerprint="c" * 64,
    )
    path = write_bundle(bundle, tmp_path / "b.json")
    validate_bundle(path)  # no raise


def test_validate_bundle_rejects_bad_hash(tmp_path: Path) -> None:
    bundle = create_bundle(
        run_id="run-1",
        runtime_adapter="local_baseline",
        generated_at="2026-06-17T12:00:00Z",
        run_record_ref="ops/run-records/run-1.json",
        run_record_hash="not-a-sha",  # wrong shape
        event_ledger_ref="ops/event-log/run-1.jsonl",
        event_ledger_hash="b" * 64,
        model_tools_fingerprint="c" * 64,
    )
    path = write_bundle(bundle, tmp_path / "b.json")
    with pytest.raises(ValueError):
        validate_bundle(path)


# ---- compare_bundles ------------------------------------------------------


def test_compare_bundles_detects_fingerprint_match() -> None:
    base = create_bundle(
        run_id="run-1",
        runtime_adapter="local_baseline",
        generated_at="2026-06-17T12:00:00Z",
        run_record_ref="ops/run-records/run-1.json",
        run_record_hash="a" * 64,
        event_ledger_ref="ops/event-log/run-1.jsonl",
        event_ledger_hash="b" * 64,
        model_tools_fingerprint="c" * 64,
        artifacts=[{"ref": "out.md", "hash": "d" * 64}],
    )
    other = dict(base)
    other["runtime_adapter"] = "openai_agents"
    other["bundle_id"] = "bundle-other"
    cmp = compare_bundles(base, other)
    assert cmp.fingerprint_match
    assert not cmp.same_adapter
    assert cmp.artifact_set_match


def test_compare_bundles_detects_artifact_drift() -> None:
    base = create_bundle(
        run_id="run-1",
        runtime_adapter="local_baseline",
        generated_at="2026-06-17T12:00:00Z",
        run_record_ref="ops/run-records/run-1.json",
        run_record_hash="a" * 64,
        event_ledger_ref="ops/event-log/run-1.jsonl",
        event_ledger_hash="b" * 64,
        model_tools_fingerprint="c" * 64,
        artifacts=[{"ref": "out.md", "hash": "d" * 64}],
    )
    other = create_bundle(
        run_id="run-1",
        runtime_adapter="openai_agents",
        generated_at="2026-06-17T12:00:00Z",
        run_record_ref="ops/run-records/run-1.json",
        run_record_hash="a" * 64,
        event_ledger_ref="ops/event-log/run-1.jsonl",
        event_ledger_hash="b" * 64,
        model_tools_fingerprint="c" * 64,
        artifacts=[{"ref": "different.md", "hash": "e" * 64}],
    )
    cmp = compare_bundles(base, other)
    assert not cmp.artifact_set_match
    assert cmp.artifact_set_left_only == ["out.md"]
    assert cmp.artifact_set_right_only == ["different.md"]


# ---- CLI helpers ----------------------------------------------------------


def test_parse_artifact_spec_minimum() -> None:
    spec = _parse_artifact_spec("ref=out.md,hash=" + "d" * 64)
    assert spec == {"ref": "out.md", "hash": "d" * 64}


def test_parse_artifact_spec_with_kind() -> None:
    spec = _parse_artifact_spec("ref=out.md, hash=" + "d" * 64 + ", kind=brief")
    assert spec["kind"] == "brief"


def test_parse_artifact_spec_missing_required_raises() -> None:
    with pytest.raises(ValueError):
        _parse_artifact_spec("ref=out.md")  # missing hash


# ---- CLI end-to-end -------------------------------------------------------


def _stage_run(tmp_path: Path) -> tuple[Path, Path]:
    rec = tmp_path / "run-record.json"
    rec.write_text('{"run_id":"run-1","produced":"ok"}', encoding="utf-8")
    log = tmp_path / "event-log.jsonl"
    log.write_text('{"event":"x"}\n', encoding="utf-8")
    return rec, log


def test_cli_bundle_create_validate_round_trip(tmp_path: Path) -> None:
    rec, log = _stage_run(tmp_path)
    bundle_out = tmp_path / "bundle.json"
    fpr = "c" * 64

    rc = main(
        [
            "bundle", "create",
            "--run-id", "run-1",
            "--runtime-adapter", "local_baseline",
            "--run-record", str(rec),
            "--event-ledger", str(log),
            "--model-tools-fingerprint", fpr,
            "--generated-at", "2026-06-17T12:00:00Z",
            "--out", str(bundle_out),
        ]
    )
    assert rc == 0
    assert bundle_out.exists()
    rc = main(["bundle", "validate", str(bundle_out)])
    assert rc == 0


def test_cli_bundle_create_resolves_hashes(tmp_path: Path) -> None:
    rec, log = _stage_run(tmp_path)
    bundle_out = tmp_path / "bundle.json"
    rc = main(
        [
            "bundle", "create",
            "--run-id", "run-1",
            "--runtime-adapter", "local_baseline",
            "--run-record", str(rec),
            "--event-ledger", str(log),
            "--model-tools-fingerprint", "c" * 64,
            "--generated-at", "2026-06-17T12:00:00Z",
            "--out", str(bundle_out),
        ]
    )
    assert rc == 0
    bundle = json.loads(bundle_out.read_text())
    assert bundle["run_record_hash"] == hashlib.sha256(rec.read_bytes()).hexdigest()
    assert bundle["event_ledger_hash"] == hashlib.sha256(log.read_bytes()).hexdigest()


def test_cli_bundle_compare(tmp_path: Path) -> None:
    rec, log = _stage_run(tmp_path)
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    for path, adapter in ((a, "local_baseline"), (b, "openai_agents")):
        rc = main(
            [
                "bundle", "create",
                "--run-id", "run-1",
                "--runtime-adapter", adapter,
                "--run-record", str(rec),
                "--event-ledger", str(log),
                "--model-tools-fingerprint", "c" * 64,
                "--generated-at", "2026-06-17T12:00:00Z",
                "--out", str(path),
            ]
        )
        assert rc == 0
    rc = main(["bundle", "compare", str(a), str(b)])
    assert rc == 0
