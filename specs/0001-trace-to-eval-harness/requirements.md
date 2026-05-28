# Requirements

### R-TTE-001: Trace JSON model

The package must accept JSON traces with `trace_id`, `input`, and `output`, plus optional `citations`, `spans`, `tool_calls`, `expected_behavior`, and `failure_tags`.

### R-TTE-002: Failed trace ingestion

The ingest CLI must map one failed trace into a YAML eval case with human-review fields and TODO markers.

### R-TTE-003: Deterministic checks

The runner must support `contains_required_text`, `does_not_contain_text`, `citation_span_present`, `tool_call_allowed`, and `refusal_required`.

### R-TTE-004: Regression reports

The runner must write JSON and Markdown reports with case, suite, and check counts.

### R-TTE-005: Local and CI gates

The repo must run tests, voice lint, and spec checks locally and in GitHub Actions.

### R-TTE-006: CDCP event-log adapter

The CLI must read CDCP JSONL event logs from a file, event-log
directory, or repo root; skip malformed lines without aborting; and
map failed gate, review finding, or incident events with explicit
trace payloads into draft eval cases that require human review before
promotion.

### R-TTE-007: Run evidence packet

The CLI must generate and validate a run evidence packet that records
run inputs, tool calls, MCP surfaces, policy decisions, approvals,
artifact diffs, gate results, trace refs, and rollback refs. The packet
is evidence for review and CI; it is not the source of truth.

### R-TTE-008: Producer identity preserved

Run evidence packets must preserve the producing Run record's `id`
as `producer_run_id` and use the same value for the top-level `run_id`
field. The generator must not synthesize substitute identifiers.

### R-TTE-009: Run record and event log ingested with provenance hashes

The generator must locate the producer Run record alongside the event
log (default convention: `<event-log>/../run-records/<run_id>.json`,
overridable via `--run-record`), record both refs in the packet, and
carry a SHA-256 hash for each: the Run record hashed under a fixed
canonicalization rule (json.dumps with `sort_keys=True`, `indent=2`,
`ensure_ascii=False`, then UTF-8 encode), the event log hashed as raw
bytes. Missing or mismatched Run records must fail the generator
loudly.

### R-TTE-010: Artifact refs and replay-equivalence pass-through

When the Run record carries `outputs[]`, the packet must surface them
as `artifact_refs` (best-effort `artifact_hashes` when refs resolve to
on-disk paths). When the Run record carries `prompt_snapshot_hash`,
`tool_schemas_snapshot_hash`, or `sandbox_image_ref`, the packet must
carry the same values through unchanged.

### R-TTE-011: Deterministic provenance hashes

Both `run_record_hash` and `event_log_hash` must be deterministic for
identical inputs: hashing the same Run record twice (even with keys
reordered) must produce identical hex, and hashing the same event log
bytes must produce identical hex.

### R-TTE-SCHEMA-001: Published schemas

The repo must publish JSON Schemas for trace, eval case, and run report shapes under `schemas/`.

### R-TTE-SCHEMA-002: Validate command

The CLI must expose `trace-to-eval validate` for trace, eval, and report inputs with clear pass and fail output.

### R-TTE-SCHEMA-003: Schema versions and fixtures

Each published schema must carry `$id` and `version`, and the repo must include positive and negative fixtures for trace, eval, and report validation.

### R-TTE-SCHEMA-004: Deterministic first gate

Schema validation and deterministic checks must stay as the first gate before any later LLM judge integration.

### R-TTE-SCHEMA-005: Run evidence schema

The repo must publish a JSON Schema for run evidence packets and
include positive and negative fixtures for validation.
