---
id: DEC-TTE-008-run-evidence-packet-preserves-producer-identity
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-008
date: 2026-05-28
status: approved
reversible: true
amends: DEC-TTE-007-run-evidence-packet-as-review-boundary
decision: |
  Run evidence packet schema bumps to v2. Every packet preserves
  producer_run_id from the producing Run record, carries
  run_record_ref + run_record_hash and event_log_ref + event_log_hash
  for provenance, and clones prompt_snapshot_hash,
  tool_schemas_snapshot_hash, sandbox_image_ref, plus artifact_refs
  and artifact_hashes from the Run record when present. The generator
  reads both the event log and the producer Run record; no more
  cdcp-{hash} synthesis.
alternatives:
  - label: keep v1 packets (cdcp-{hash} synthesized run_id)
    rejected_because: |
      Codex's review found the v1 packet "does not yet prove replay
      equivalence". A synthesized run_id cannot be linked back to the
      Run record that produced it; the packet held only event-log
      fields and dropped the replay-equivalence hashes the Run
      record already carries. Engineering-grade demands packet
      provenance.
  - label: add producer_run_id only, skip the hashes
    rejected_because: |
      Identity alone is fragile. Without run_record_hash and
      event_log_hash a downstream consumer cannot detect that the
      referenced files have changed since the packet was written.
      Hashes turn the packet into a real bridge.
  - label: rewrite v1 packets in place (no version bump)
    rejected_because: |
      Existing consumers may have stored copies of v1 packets. A
      schema_version bump 1.0.0 -> 2.0.0 plus a $id v1 -> v2 swap
      makes the contract change explicit and lets consumers reject
      stale packets at validation time.
rationale: |
  The producer side (every product repo's emitter) now writes typed
  events and full Run records with replay-equivalence evidence. The
  consumer side (this packet generator) was still flattening events
  into a v1 packet that lost the bridge. v2 closes that gap by
  reading the Run record alongside the event log, preserving the
  producer's id, and hashing both inputs deterministically. The
  packet becomes a real handshake: any consumer can resolve
  run_record_ref + run_record_hash to inspect (and re-verify) the
  exact Run that the packet describes.
evidence:
  - kind: decision
    ref: decisions/DEC-TTE-007-run-evidence-packet-as-review-boundary.md
  - kind: schema
    ref: schemas/run-evidence.schema.json
  - kind: code
    ref: trace_to_eval/run_evidence.py
  - kind: test
    ref: tests/test_run_evidence.py
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
rollback: |
  Drop the new required fields (producer_run_id, run_record_ref,
  run_record_hash, event_log_ref, event_log_hash) plus the optional
  replay-equivalence and artifact fields from
  schemas/run-evidence.schema.json. Revert the schema $id back to v1
  and schema_version to 1.0.0. Restore the v1 synthesized
  run_id = cdcp-{packet_hash} path in
  build_run_evidence_from_cdcp_events and remove the --run-record
  CLI flag. Re-generate examples/run_evidence packets against the
  v1 generator. The new fields are additive, so this rollback is
  bounded.
owner: science.eval_curator
---

## decision

Run evidence packet schema bumps to v2. Every packet preserves
`producer_run_id` from the producing Run record (R-TTE-008), carries
`run_record_ref` + `run_record_hash` and `event_log_ref` +
`event_log_hash` for provenance (R-TTE-009), and clones
`prompt_snapshot_hash`, `tool_schemas_snapshot_hash`,
`sandbox_image_ref`, plus `artifact_refs` and `artifact_hashes` from
the Run record when present (R-TTE-010). The generator reads both the
event log and the producer Run record; no more `cdcp-{hash}`
synthesis. Provenance hashes are deterministic for identical inputs
under a fixed canonicalization rule (R-TTE-011). R-TTE-007 stays as
the review-boundary anchor; this DEC amends it without superseding
it.

## alternatives

- Keep v1 packets with the synthesized `cdcp-{hash}` run_id. Rejected
  because Codex's review found the v1 packet "does not yet prove
  replay equivalence": the packet had no way to link back to the
  producer's Run record, and the replay-equivalence hashes the Run
  record already carries were dropped on the floor.
- Add `producer_run_id` only, skip the hashes. Rejected because
  identity alone is fragile: without `run_record_hash` and
  `event_log_hash` a downstream consumer cannot detect that the
  referenced files have changed since the packet was written.
- Rewrite v1 packets in place without a version bump. Rejected
  because existing consumers may have stored copies of v1 packets, and
  a `$id` swap from `v1` to `v2` plus `schema_version` `1.0.0` ->
  `2.0.0` makes the contract change visible at validation time.

## rationale

The producer side (every product repo's emitter) now writes typed
events and full Run records with replay-equivalence evidence
(DEC-CDCP-011 on athena-site, plus the per-product DECs that adopt
it). The consumer side (this packet generator) was still flattening
events into a v1 packet that lost the bridge between the producer's
Run record and the packet a reviewer reads. v2 closes that gap.

The generator now reads the Run record alongside the event log,
auto-discovering at `<event-log>/../run-records/<run_id>.json` and
accepting a `--run-record` override for non-standard layouts. The
packet's `run_id` field equals `producer_run_id` so existing consumers
that read `run_id` keep working while gaining provenance. Hashes use
a fixed canonicalization rule for the Run record (`json.dumps` with
`sort_keys=True`, `indent=2`, `ensure_ascii=False`, then UTF-8
encode) and raw bytes for the append-only event log.

## evidence

- `decisions/DEC-TTE-007-run-evidence-packet-as-review-boundary.md`
- `schemas/run-evidence.schema.json`
- `trace_to_eval/run_evidence.py`
- `tests/test_run_evidence.py`
- `specs/0001-trace-to-eval-harness/requirements.md`

## rollback

Drop the new required fields (`producer_run_id`, `run_record_ref`,
`run_record_hash`, `event_log_ref`, `event_log_hash`) plus the
optional replay-equivalence and artifact fields from
`schemas/run-evidence.schema.json`. Revert the schema `$id` back to v1
and `schema_version` to `1.0.0`. Restore the v1 synthesized
`run_id = cdcp-{packet_hash}` path in
`build_run_evidence_from_cdcp_events` and remove the `--run-record`
CLI flag. Re-generate `examples/run_evidence` packets against the v1
generator. The new fields are additive, so this rollback is bounded.
