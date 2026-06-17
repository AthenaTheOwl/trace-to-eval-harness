"""Run-bundle primitives — the runtime-agnostic envelope.

A run bundle is a higher-level container that points at one run's:
- Run record (canonical)
- Event ledger (canonical)
- (Optional) provider-specific trace export
- (Optional) sandbox manifest
- Model+tools fingerprint
- Emitted artifacts
- Replay status

Framework adapters (local_baseline, openai_agents, langgraph,
modal_sandbox, ...) all emit bundles. The comparison harness reads
them through one schema so the question shifts from "which framework"
to "which adapter produced higher-quality evidence."

This module ships three primitives:

- ``create_bundle()``: assemble a bundle dict from references + hashes
- ``validate_bundle()``: JSON-schema-validate a bundle file
- ``compare_bundles()``: diff two bundles produced for the same task,
  highlighting fingerprint match, artifact agreement, and replay status
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .validation import validate_document


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


SCHEMA_VERSION = "1.0.0"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_bundle_id(
    run_id: str,
    runtime_adapter: str,
    model_tools_fingerprint: str,
) -> str:
    """Deterministic bundle id from the core identity fields.

    Uses the run_id + adapter + fingerprint trio so two bundles with the
    same provenance get the same id. Different adapters or different
    fingerprints land at different ids — that's the cross-run distinction
    the comparison harness needs.
    """
    payload = json.dumps(
        {"run_id": run_id, "runtime_adapter": runtime_adapter, "fpr": model_tools_fingerprint},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "bundle-" + hashlib.sha256(payload).hexdigest()[:16]


def fingerprint_prompts_and_tools(
    prompts: list[str], tool_schemas: list[dict] | None = None
) -> str:
    """Canonical SHA-256 fingerprint of the (prompts, tool_schemas) pair.

    Both adapters and consumers compute the fingerprint the same way:
    JSON-canonicalize the pair (sorted keys, no whitespace) and sha256.
    Two runs with the same fingerprint executed against the same prompt
    + tool surface, regardless of adapter.
    """
    payload = json.dumps(
        {"prompts": list(prompts), "tool_schemas": list(tool_schemas or [])},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def create_bundle(
    *,
    run_id: str,
    runtime_adapter: str,
    generated_at: str,
    run_record_ref: str,
    run_record_hash: str,
    event_ledger_ref: str,
    event_ledger_hash: str,
    model_tools_fingerprint: str,
    artifacts: list[dict[str, str]] | None = None,
    trace_ref: str | None = None,
    trace_hash: str | None = None,
    sandbox_manifest_ref: str | None = None,
    sandbox_manifest_hash: str | None = None,
    adapter_version: str | None = None,
    replay_status: str = "not_attempted",
    replay_notes: str | None = None,
    cost_usage: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Build a run-bundle dict matching schemas/run-bundle.schema.json.

    Pure data; no I/O. Validate the returned dict via ``validate_bundle()``.
    """
    bundle: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": canonical_bundle_id(run_id, runtime_adapter, model_tools_fingerprint),
        "run_id": run_id,
        "runtime_adapter": runtime_adapter,
        "generated_at": generated_at,
        "run_record_ref": run_record_ref,
        "run_record_hash": run_record_hash,
        "event_ledger_ref": event_ledger_ref,
        "event_ledger_hash": event_ledger_hash,
        "model_tools_fingerprint": model_tools_fingerprint,
        "artifacts": list(artifacts or []),
        "replay_status": replay_status,
    }
    if adapter_version is not None:
        bundle["adapter_version"] = adapter_version
    if trace_ref is not None:
        bundle["trace_ref"] = trace_ref
        if trace_hash is not None:
            bundle["trace_hash"] = trace_hash
    if sandbox_manifest_ref is not None:
        bundle["sandbox_manifest_ref"] = sandbox_manifest_ref
        if sandbox_manifest_hash is not None:
            bundle["sandbox_manifest_hash"] = sandbox_manifest_hash
    if replay_notes is not None:
        bundle["replay_notes"] = replay_notes
    if cost_usage is not None:
        bundle["cost_usage"] = cost_usage
    if notes:
        bundle["notes"] = list(notes)
    return bundle


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_bundle(path: Path, *, schema_dir: Path | None = None) -> None:
    """Validate a bundle file against the schema. Raises on failure.

    Delegates to the existing validation surface so error formatting
    matches the rest of the CLI.
    """
    result = validate_document("run-bundle", path, schema_dir=schema_dir)
    if not result.passed:
        issues = "; ".join(f"{i.location}: {i.message}" for i in result.issues)
        raise ValueError(f"{path} does not match {result.schema_id}: {issues}")


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class BundleComparison:
    """Side-by-side comparison of two bundles produced for the same task."""

    left_id: str
    right_id: str
    fingerprint_match: bool
    same_run_id: bool
    same_adapter: bool
    artifact_set_match: bool
    artifact_set_left_only: list[str]
    artifact_set_right_only: list[str]
    replay_status_match: bool

    def summary_line(self) -> str:
        parts = [
            f"L={self.left_id} R={self.right_id}",
            "fingerprint=" + ("MATCH" if self.fingerprint_match else "DIFFER"),
            "adapter=" + ("SAME" if self.same_adapter else "DIFFER"),
            "artifacts=" + ("MATCH" if self.artifact_set_match else "DIFFER"),
            f"replay=L:{self.replay_status_match}",
        ]
        return " | ".join(parts)


def compare_bundles(left: dict[str, Any], right: dict[str, Any]) -> BundleComparison:
    """Compare two bundles. Does not require them to be from the same adapter.

    The interesting comparisons:
    - same fingerprint = same prompt + tool surface
    - same artifact-ref set = produced equivalent outputs
    - replay_status match = same observability outcome
    """
    left_artifacts = sorted({a["ref"] for a in left.get("artifacts", [])})
    right_artifacts = sorted({a["ref"] for a in right.get("artifacts", [])})
    return BundleComparison(
        left_id=left.get("bundle_id", "?"),
        right_id=right.get("bundle_id", "?"),
        fingerprint_match=(
            left.get("model_tools_fingerprint") == right.get("model_tools_fingerprint")
        ),
        same_run_id=left.get("run_id") == right.get("run_id"),
        same_adapter=left.get("runtime_adapter") == right.get("runtime_adapter"),
        artifact_set_match=left_artifacts == right_artifacts,
        artifact_set_left_only=sorted(set(left_artifacts) - set(right_artifacts)),
        artifact_set_right_only=sorted(set(right_artifacts) - set(left_artifacts)),
        replay_status_match=left.get("replay_status") == right.get("replay_status"),
    )


def read_bundle(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_bundle(bundle: dict[str, Any], path: Path) -> Path:
    """Persist a bundle to disk with canonical JSON formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


__all__ = [
    "SCHEMA_VERSION",
    "BundleComparison",
    "canonical_bundle_id",
    "compare_bundles",
    "create_bundle",
    "fingerprint_prompts_and_tools",
    "read_bundle",
    "validate_bundle",
    "write_bundle",
]
