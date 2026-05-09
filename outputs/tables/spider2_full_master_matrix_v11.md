# Spider2 v11 master matrix — Phase 13 snapshot

_Generated: 2026-05-08. **One real FULL** (DBT 68, 13.2%). Three gate-failed pilots (Snow v11, Lite-BQ v10, prior Lite-SF v9)._

| benchmark | n_full | n_pilot v11 | parse_ok | execute_ok | schema_valid | task_success | non-comp | status |
|---|---:|---:|---:|---:|---:|---:|:---:|---|
| **Spider2-DBT v4** | 68 | — | — | — | — | **9 (13.2%)** | no | ✅ FULL DONE (Phase 11) |
| **Spider2-Snow canonical** | 547 | 10 | 0 (0%) | 0 (0%) | **1 (10%)** | — | no | ❌ FULL deferred (gate ≥30% failed) |
| **Spider2-Lite — BQ lane** | 205 | 10 | 0 (0%) | 0 (0%) | — (no validator yet) | — | no | ❌ FULL deferred (gate ≥30% failed) |
| **Spider2-Lite — SF lane** | 207 | — | — | — | — | — | no | not piloted v11 yet |
| **Spider2-Lite — SQLite** | 135 | — | — | — | — | — | **YES** | non-comparable always |

> The `schema_valid` column is unique to v11+. v9/v10 ran SQL straight
> to the engine; v11 pre-validates via sqlglot+catalog and only sends
> schema-valid candidates to dry_run.

## Comparison v10 → v11 (same 10-task slice, Snow lane)

| metric | v10 | **v11** | delta |
|---|---:|---:|---:|
| chosen_schema_valid | 0 | **1** | **+1** |
| object_not_found at engine | 7 | **0** | **-7** ✅ (validator gate stops them) |
| schema_invalid (validator-rejected) | n/a | 9 | new bucket |
| syntax (SF) | 4 | 1 | -3 |
| parse_ok (SF dry_run) | 0 | 0 | 0 |
