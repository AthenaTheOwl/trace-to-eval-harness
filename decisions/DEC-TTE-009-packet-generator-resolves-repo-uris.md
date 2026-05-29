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
systems_map: |
  Producer-consumer URI contract across the CDCP portfolio. Producers
  emit content-addressed refs (`repo://<repo>@<sha>/<path>`) and
  opaque artifact refs (`artifact://<repo>/<id>`); the consumer-side
  resolver (this repo's `trace_to_eval/uri.py`) parses both, opens
  the repo URIs through a configurable `portfolio_root`, and skips
  artifact URIs as opaque. The same pattern applies to any
  cross-repo consumer that has to read producer evidence at a
  pinned commit.
transferable_principle: |
  Any cross-repo evidence pipeline needs a content-addressed ref
  scheme (commit-pinned for files, opaque for logical artifacts)
  plus a consumer-side resolver that defaults to local checkout
  but accepts a portfolio_root override. Schema-level `anyOf`
  acceptance of both URI and path forms keeps interop with legacy
  emitters while marking the URI form as preferred.
falsification_test: |
  If a Round 6 producer ledger that emits `repo://` URIs in
  `sandbox_image_ref` causes the packet generator to either crash,
  silently write missing hashes, or open the URI as a relative path,
  the resolver contract is falsified. Equivalently: if two consumer
  repos resolve the same `repo://` URI to different bytes given the
  same portfolio_root, the content-addressing claim is falsified.
adoption_ladder:
  minimum_viable: |
    Resolver in `trace_to_eval/uri.py`; schema bumps to v2.1.0 with
    `anyOf` ref patterns; example packets regenerated.
  mid_adoption: |
    `--portfolio-root` CLI flag wired through every command that
    reads a Run record; `PORTFOLIO_ROOT` env var documented;
    cross-repo example ledger added under `tests/fixtures/`.
  full_adoption: |
    Every consumer repo in the portfolio reads URIs through the
    same resolver shape; path-form refs deprecated in Round 7;
    schema bumps to v3 with URI-only ref patterns.
  monitoring_signals:
    - URI-vs-path ref ratio in shipped packets (tracked per release)
    - resolver-failure exit code count per CI run
    - cross-repo packet portability (replay-equivalence across machines)
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
