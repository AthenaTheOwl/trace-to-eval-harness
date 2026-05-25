# dreams

A weekly offline-cognition pass that reads the last N days of runs,
postmortems, and gate reports, then proposes promotion candidates.
Dreams name what we learned. Every candidate is human-gated; no CI
job auto-applies a dream output.

## Folder shape

```
dreams/
  README.md           (this file)
  YYYY-WNN/           (one folder per ISO week, lands when the dream job ships)
    report.md         (human-readable narrative)
    meta.yaml         (structured metadata)
    candidates/       (one .md per candidate; YAML front-matter per dream-output.schema.json)
```

The first weekly folder lands in a later pass; the README reserves
the shape now.

## The eight dream modes

The cross-repo `dream-output.schema.json` defines mode strings; the
list below documents the eight cognitive modes the dream job
exercises.

1. **memory_consolidation** — read the last week of runs and roll
   up recurring observations into a `memory_update` candidate
   against a target memory file.
2. **failure_clustering** — read the last week of failures and
   cluster by root cause. Each cluster becomes a `backlog_item`
   candidate.
3. **adversarial_simulation** — generate inputs designed to break a
   known-fragile path. Each reproducible breakage becomes a
   `test_generation` candidate.
4. **counterfactual_replay** — re-run past decisions with one input
   changed; flag cases where the changed input would have flipped
   the verdict.
5. **skill_extraction** — recognize a pattern that has repeated
   three or more times in commits or runs; package it into a
   `skill_patch` candidate.
6. **golden_test_generation** — find inputs that produced a known-good
   output and propose them as gate tests so the output stays stable.
7. **redundancy_pruning** — find rules, checks, or DECs that have
   not fired or been touched in a long time; propose pruning.
8. **release_retrospective** — read the last week of release ledger
   entries; cluster by axis (gate misfires, scope creep, test gaps);
   propose process changes.

## Gating rule

Every candidate carries `human_review_required: true` per the
cross-repo schema default. The
`.agents/policies/dream-candidates-require-human-approval.yaml`
policy makes the rule enforceable rather than aspirational.
