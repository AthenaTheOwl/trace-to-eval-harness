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
