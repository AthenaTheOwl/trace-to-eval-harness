---
id: DEC-TTE-009-packet-generator-resolves-repo-uris
spec: specs/0001-trace-to-eval-harness/
requirement: R-TTE-012
date: 2026-05-29
status: approved
reversible: true
amends: DEC-TTE-008-run-evidence-packet-preserves-producer-identity
decision: |
  The run evidence packet generator accepts repo:// and artifact://
  URIs in every ref field it reads from producer Run records and event
  ledgers, and the run-evidence schema bumps to v2.1.0 with anyOf
  pattern constraints that accept both URI forms and free-form paths.
  Packets pass producer-side URIs through verbatim into
  run_record_ref, event_log_ref, sandbox_image_ref, and
  artifact_refs[].ref where the producer emits them; they fall back
  to portfolio-relative paths only when the producer Run record
  carries no repo:// sandbox_image_ref.
alternatives:
  - label: keep ref fields opaque and reject URI-bearing ledgers
    rejected_because: |
      Round 6 Phase 2 just migrated 4 product repos to emit URIs in
      their Run records. Rejecting URI-bearing ledgers would silently
      break every downstream consumer that reads a packet generated
      from a post-Phase-2 ledger. The whole point of Phase 3 is to
      catch the consumer up to the producers.
  - label: resolve URIs at packet read time but emit only legacy paths
    rejected_because: |
      A packet that strips URIs is not portable. The repo://<repo>@<sha>
      form carries the producer commit SHA the run executed under;
      replay-strict consumers need that SHA to verify they are running
      against the right tree. Forcing all packets to local paths
      throws that information away.
  - label: replace path-form refs entirely (require URIs)
    rejected_because: |
      Phase 2 emitters are migrated, but the spec calls Round 6 the
      migration round. A consumer that hard-required URIs would refuse
      any pre-Round-6 packet that a reviewer might still have stored.
      The anyOf clause keeps interop with legacy packets while marking
      URIs as the preferred form. Round 7 may deprecate the path form;
      Round 6 keeps both.
rationale: |
  DEC-CDCP-014 in athena-site formalized two URI schemes:
  repo://<repo-name>@<sha>/<rel-path> for files at a specific commit,
  and artifact://<repo-name>/<artifact-id> for opaque logical
  artifacts. Phase 2 wired every product repo's emitter to produce
  them. Without a consumer-side resolver the bridge collapses: the
  generator would treat URIs as relative paths, fail to open the
  files, and either crash or write packets with missing hashes. The
  resolver in trace_to_eval/uri.py does the parse-and-resolve job
  once; build_run_evidence_from_cdcp_events threads a portfolio_root
  through every site that reads a file. The schema's anyOf clause is
  the interop contract: consumers MUST accept both forms, producers
  SHOULD emit URIs.
evidence:
  - kind: decision
    ref: decisions/DEC-TTE-008-run-evidence-packet-preserves-producer-identity.md
  - kind: schema
    ref: schemas/run-evidence.schema.json
  - kind: code
    ref: trace_to_eval/uri.py
  - kind: code
    ref: trace_to_eval/run_evidence.py
  - kind: test
    ref: tests/test_uri.py
  - kind: test
    ref: tests/test_run_evidence.py
  - kind: spec
    ref: specs/0001-trace-to-eval-harness/requirements.md
rollback: |
  Revert the schema_version + $id back to 2.0.0 / v2 and drop the
  anyOf clauses from run_record_ref, event_log_ref, sandbox_image_ref,
  and artifact_refs[].ref. Remove the URI-detection branches from
  _load_run_record and _build_artifact_refs_and_hashes; drop the
  --portfolio-root CLI flag; delete trace_to_eval/uri.py and
  tests/test_uri.py. Re-generate the example packets against the
  reverted generator. The new fields are additive and behind a
  detection branch (URIs only flow through when the producer emits
  them), so the rollback path is bounded.
owner: science.eval_curator
---

## decision

The run evidence packet generator accepts `repo://` and `artifact://`
URIs in every ref field it reads from producer Run records and event
ledgers (R-TTE-012), and the run-evidence schema bumps to v2.1.0
with `anyOf` pattern constraints that accept both URI forms and
free-form paths (R-TTE-013). Packets pass producer-side URIs through
verbatim into `run_record_ref`, `event_log_ref`,
`sandbox_image_ref`, and `artifact_refs[].ref` where the producer
emits them; they fall back to portfolio-relative paths only when the
producer Run record carries no `repo://` `sandbox_image_ref`
(R-TTE-014). DEC-TTE-007 and DEC-TTE-008 stay as the review-boundary
and producer-identity anchors; this DEC amends DEC-TTE-008 without
superseding it.

## alternatives

- Keep ref fields opaque and reject URI-bearing ledgers. Rejected
  because Round 6 Phase 2 just migrated 4 product repos to emit
  URIs; rejecting their ledgers would silently break every
  downstream consumer that reads a post-Phase-2 packet.
- Resolve URIs at read time but emit only legacy paths into the
  packet. Rejected because the `repo://<repo>@<sha>` form carries
  the commit SHA the run executed under; replay-strict consumers
  need it to verify they are running against the right tree.
- Replace path-form refs entirely (require URIs). Rejected because
  Round 6 is the migration round, not the deprecation round.
  Pre-Round-6 packets a reviewer might still have stored should
  keep validating. The `anyOf` clause keeps interop while marking
  URIs as preferred.

## rationale

`DEC-CDCP-014` in athena-site formalized two URI schemes:
`repo://<repo-name>@<sha>/<rel-path>` for files at a specific
commit, and `artifact://<repo-name>/<artifact-id>` for opaque
logical artifacts. Phase 2 wired every product repo's emitter to
produce them. Without a consumer-side resolver the bridge
collapses: the generator would treat URIs as relative paths, fail
to open the files, and either crash or write packets with missing
hashes.

The resolver in `trace_to_eval/uri.py` does the parse-and-resolve
job once; `build_run_evidence_from_cdcp_events` threads a
`portfolio_root` through every site that reads a file (default:
`$PORTFOLIO_ROOT` env var, else this repo's parent). The schema's
`anyOf` clause is the interop contract: consumers MUST accept both
forms, producers SHOULD emit URIs.

## evidence

- `decisions/DEC-TTE-008-run-evidence-packet-preserves-producer-identity.md`
- `schemas/run-evidence.schema.json`
- `trace_to_eval/uri.py`
- `trace_to_eval/run_evidence.py`
- `tests/test_uri.py`
- `tests/test_run_evidence.py`
- `specs/0001-trace-to-eval-harness/requirements.md`

## rollback

Revert the `schema_version` + `$id` back to `2.0.0` / `v2` and drop
the `anyOf` clauses from `run_record_ref`, `event_log_ref`,
`sandbox_image_ref`, and `artifact_refs[].ref`. Remove the
URI-detection branches from `_load_run_record` and
`_build_artifact_refs_and_hashes`; drop the `--portfolio-root` CLI
flag; delete `trace_to_eval/uri.py` and `tests/test_uri.py`.
Re-generate the example packets against the reverted generator.
The new fields are additive and behind a detection branch (URIs
only flow through when the producer emits them), so the rollback
path is bounded.
