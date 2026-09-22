# Repeated-run reliability report

- Reports: 3
- Cases: 2
- Missing attempts: 0
- Pass@1: 100.0%
- Pass@3: 100.0%
- Pass^3: 50.0%
- Stable cases: 50.0%

| Case | Suite | Passed | Observed | Pass@1 | Pass@k | Pass^k | Stable |
|---|---|---:|---:|---:|---:|---:|---:|
| approval_sequence | state_integrity | 3/3 | 3/3 | yes | yes | yes | yes |
| invoice_terminal_state | state_integrity | 2/3 | 3/3 | yes | yes | no | no |
