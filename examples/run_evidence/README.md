# examples/run_evidence

This directory holds canonical example packets produced from real CDCP
event logs. Each `*.packet.json` validates against
[`schemas/run-evidence.schema.json`](../../schemas/run-evidence.schema.json).

## First example: `run-cb524eb06115.packet.json`

This example was generated from a procurement-negotiation-lab factory
run on 2026-05-27. The factory's run-evidence emitter
(`procurement-negotiation-lab/src/procurement_lab/run_evidence.py`,
landed in DEC-FACTORY-007) wrote a conformant Event ledger at
`ops/event-ledger/run-cb524eb06115.jsonl`. The packet here is what
this repo's `evidence from-cdcp-events` CLI produced when fed that
ledger.

### How to regenerate

```powershell
# From this repo's root.
python -m trace_to_eval evidence from-cdcp-events `
  ../procurement-negotiation-lab/ops/event-ledger/run-cb524eb06115.jsonl `
  --out examples/run_evidence/run-cb524eb06115.packet.json

python -m trace_to_eval evidence validate `
  examples/run_evidence/run-cb524eb06115.packet.json
```

The second command exits 0; the packet matches the schema.

### Why this example matters

The packet is the first end-to-end proof of the bridge:

- The source-of-truth Run schema in
  [`athena-site/ops/schemas/run.schema.json`](https://github.com/AthenaTheOwl/athena-site/blob/main/ops/schemas/run.schema.json)
  carries six replay-equivalence fields (amended in DEC-CDCP-011).
- The emitter side lands in procurement-negotiation-lab:
  [`DEC-FACTORY-007`](https://github.com/AthenaTheOwl/procurement-negotiation-lab/blob/main/decisions/DEC-FACTORY-007-factory-emits-conformant-run-evidence.md)
  ships the factory wiring; every pipeline run now writes a Run
  record plus an Event ledger.
- The consumer side lands in this repo:
  [`DEC-TTE-007`](../../decisions/DEC-TTE-007-run-evidence-packet-as-review-boundary.md)
  fixes the run-evidence packet as the review boundary; the
  `evidence from-cdcp-events` CLI reads any CDCP event log and
  produces a packet that downstream review surfaces can consume
  without knowing how the producer is wired.

Without an emitter the schema fields are dead letters. Without a
consumer the packet has no review surface. This packet is the
handshake.
