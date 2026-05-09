# Spider2 v8 master matrix — pilot snapshot

_Generated: 2026-05-08. PILOT-only numbers — FULL benchmarks deferred to a follow-up session._

| benchmark | n_full | n_pilot | parse_ok | execute_ok | task_success | non_comparable | status |
|---|---:|---:|---:|---:|---:|:---:|---|
| **Spider2-Snow** | 547 | 3 | 0 | 0 | — | no | PILOT only |
| **Spider2-Lite — BQ lane** | 205 | 1 | 0 | 0 | — | no | PILOT only |
| **Spider2-Lite — SF lane** | 207 | 1 | 0 | 0 | — | no | PILOT only |
| **Spider2-Lite — SQLite stub** | 135 | 1 | 0 | 0 | — | **YES** | PILOT only / non-comparable |
| **Spider2-DBT v4** | 68 | 1 | — | run_rc=0 ✓ | **1 (100%)** | no | PILOT only |

> Do **not** average across rows. Each is a separate benchmark with a
> different evaluation contract.
> SQLite-stub row is informational only; it does not contribute to any
> benchmark score.

## Per-benchmark error taxonomy (PILOT)

| benchmark | top error | count |
|---|---|---:|
| Spider2-Snow | `wrong_dialect` | 2 |
| Spider2-Snow | `object_not_found` | 1 |
| Spider2-Lite BQ | BQ literal-cast `unknown` | 1 |
| Spider2-Lite SF | `object_not_found` | 1 |
| Spider2-Lite SQLite | `sqlite_db_missing` | 1 |
| Spider2-DBT v4 | `done` | 1 |
