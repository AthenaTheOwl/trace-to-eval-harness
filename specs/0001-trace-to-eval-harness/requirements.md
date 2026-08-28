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

### R-TTE-012: URI-bearing ref fields resolve through portfolio_root

The packet generator must accept `repo://<repo>@<sha>/<path>` and
`artifact://<repo>/<id>` URIs in every ref field it reads from a
producer Run record or event ledger (`sandbox_image_ref`,
`Run.inputs[].ref`, `Run.outputs[].artifact_id`). The generator must
resolve `repo://` URIs to local paths under a configurable
`portfolio_root` (CLI flag `--portfolio-root`, env var
`PORTFOLIO_ROOT`, default = this repo's parent directory) before
opening files for hashing. `artifact://` URIs are opaque and must not
be opened as files; the generator omits them from `artifact_hashes`.

### R-TTE-013: Packet schema v2.1 ref patterns accept URI or path

The run-evidence schema's ref fields (`run_record_ref`,
`event_log_ref`, `sandbox_image_ref`, `artifact_refs[].ref`) must use
an `anyOf` clause that accepts the URI pattern AND a free-form path
pattern. The version + `$id` must bump together when the contract
shifts (2.0.0 / v2 -> 2.1.0 / v2-1 for this change).

### R-TTE-014: Producer URIs pass through unchanged

When the producer Run record carries a `repo://` `sandbox_image_ref`,
the generator must emit `run_record_ref` and `event_log_ref` as
`repo://<repo>@<sha>/ops/run-records/<id>.json` and
`repo://<repo>@<sha>/ops/event-ledger/<file>.jsonl` so packets are
portable across machines. `artifact_refs[].ref` must pass through
verbatim from `Run.outputs[].artifact_id`. Legacy producers
(no `repo://` `sandbox_image_ref`) keep getting portfolio-relative
posix paths.

### R-TTE-015: CI run-evidence gates workflow exists and triggers correctly

The repo must publish a `.github/workflows/run-evidence-gates.yml`
workflow that triggers on every pull request and on every push to
`main`, runs on `ubuntu-latest`, and pins Python 3.11. The workflow
binds the trace-to-eval-harness side of the DEC-CDCP-015 CI
enforcement contract to a named GitHub Actions check so the contract
mapping is legible from the Actions tab.

### R-TTE-016: All example packets validate as a CI gate

The `all-example-packets-validate` job in
`run-evidence-gates.yml` must iterate every
`examples/run_evidence/*.packet.json` file, run
`python -m trace_to_eval evidence validate <path>` on each, and fail
the build if any packet fails validation or if the glob is empty.

### R-TTE-017: URI resolver tests run as a CI gate

The `uri-resolver-tests` job in `run-evidence-gates.yml` must run
`pytest tests/test_uri.py tests/test_run_evidence.py` so the Round 6
URI-handling coverage is bound to a named CI check rather than
folded into the general pytest run.

### R-TTE-018: No continue-on-error on contract gates

No step in `.github/workflows/run-evidence-gates.yml` may carry
`continue-on-error: true` or `if: ${{ failure() }}` marker that turns
a contract gate informational. Every gate in the DEC-CDCP-015
contract that applies to this repo must block the build on failure.

### R-TTE-019: URI parser property tests

The repo must publish Hypothesis-driven property tests for the URI
parser at `tests/test_uri_properties.py`. Tests must sweep the
`repo://` and `artifact://` grammars: every well-formed URI must
round-trip through `parse_repo_uri` and `parse_artifact_uri`, and
every documented malformed input (short SHA, long SHA, missing `@`,
missing path slash, uppercase repo, empty repo, digit-leading repo)
must reject deterministically.

### R-TTE-020: validate-chain subcommand exists

The CLI must expose `trace-to-eval validate-chain <ledger>` which
runs the full DEC-CDCP-015 chain in one shot: validate every event
against the cached `event.schema.json`, locate the producer Run
record (auto-discovery or `--run-record` override), regenerate the
packet via the existing pipeline, re-validate the packet against
`run-evidence.schema.json`, then run four cross-checks
(`prompt_snapshot_hash`, `tool_schemas_snapshot_hash`,
`gate_results_summary`, `fields_populated`) across packet, Run
record, and ledger. The OK path prints a JSON summary; the FAIL
path names the failing stage.

### R-TTE-021: Audit log appends on success

The CLI must append a structured JSONL entry to `ops/audit-log.jsonl`
on every successful invocation of `evidence from-cdcp-events` and
`validate-chain`. Each entry must carry `timestamp`, `command`,
`ledger_path`, `run_id`, `result`, and `packet_hash` keys (any
unused field may be null). The log file is gitignored;
`ops/audit-log.example.jsonl` is checked in as a shape reference.

### R-TTE-022: audit summary subcommand aggregates the log

The CLI must expose `trace-to-eval audit summary` which reads the
audit log and prints aggregate stats: total invocations, breakdown
by command, breakdown by result, and the top N ledger paths by
invocation count. A `--since YYYY-MM-DD` flag must filter entries by
timestamp.

### R-TTE-023: Schemas-cache mirrors post-DEC-CDCP-020 shape

The cached cross-repo schemas under `ops/schemas-cache/`
(`decision.schema.json`, `dream-output.schema.json`,
`run.schema.json`) must match the post-DEC-CDCP-020 athena-site
sources byte-for-byte so the four new optional fields
(`systems_map`, `transferable_principle`, `falsification_test`,
`adoption_ladder`) round-trip through this repo's validators.
`check_schema_cache_freshness.py` must exit 0 against the current
athena-site sources.

### R-TTE-024: AGENTS.md names the systems-thinking discipline

`.agents/AGENTS.md` must carry a top-level section titled
"Systems-thinking discipline (per DEC-CDCP-020)" that names the
four optional fields, the warning-then-ratchet sequence, and the
fallback string for pure-design choices where a falsification
test does not apply.

### R-TTE-025: validate_decisions emits non-blocking warning

`scripts/validate_decisions.py` must emit a stderr warning when a
DEC with `status: approved` is missing any of the four
systems-thinking fields. The script must exit 0 when only
warnings are present (schema-validation violations still exit 1).
The warning must name the missing field(s) and the DEC path.

### R-TTE-026: Last three DECs retrofitted

`DEC-TTE-009`, `DEC-TTE-010`, and `DEC-TTE-011` must populate all
four systems-thinking fields with substantive content (not
placeholders). The retrofit serves as the demonstration of what
the discipline looks like in practice; earlier DECs stay
un-retrofitted and surface as warnings until the 30-day amendment.

### R-TTE-027: Terminal-state and extra-effect checks

The deterministic runner must support exact terminal-state comparison and an
allowlist check over structured effects. A correct final message must not mask
the wrong stored state or an unapproved side effect.

### R-TTE-028: Repeated-run reliability report

The CLI must aggregate two or more ordered run reports into case-level pass@1,
pass@k, pass^k, stability, and missing-attempt measures. A missing case occupies
its attempt slot and counts as a failed attempt.

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

### R-TTE-SCHEMA-006: Reliability report schema

The repo must publish and validate a versioned JSON Schema for repeated-run
reliability reports, with positive and negative fixtures.
