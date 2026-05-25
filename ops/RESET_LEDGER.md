# RESET_LEDGER

Every force-push, history rewrite, or production rollback against
this repo lands here. The entry appears in the same push that
performs the rewrite. Silent rewrites are forbidden.

## Format

```
## YYYY-MM-DD HH:MM TZ — <one-line cause>

- operator: <github handle or agent id>
- kind: force-push | history-rewrite | rollback
- ref: <branch or tag>
- from: <SHA>
- to: <SHA>
- cause: <one paragraph naming the trigger>
- recovery: <what the operator did to verify the new state>
```

## Entries

No entries. The repo has not had a force-push, history rewrite, or
rollback since init.
