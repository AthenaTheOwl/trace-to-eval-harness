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

