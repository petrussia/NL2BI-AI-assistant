# Spider2 v13 master matrix — Phase 15 snapshot

_Generated: 2026-05-08. **One real FULL** (DBT 68 = 13.2%). Two
gate-failed pilots this phase (Snow v13, BQ v12)._

| benchmark | n_full | n_pilot v13 | parse_ok | execute_ok | schema_valid | task_success | non-comp | status |
|---|---:|---:|---:|---:|---:|---:|:---:|---|
| **Spider2-DBT v4** | 68 | — | — | — | — | **9 (13.2%)** | no | ✅ FULL DONE (Phase 11) |
| **Spider2-Snow canonical** | 547 | 9 (v13, crash on 10) | 0 (0%) | 0 (0%) | **0 (0%)** | — | no | ❌ FULL deferred — gate failed |
| **Spider2-Lite — BQ lane** | 205 | 10 (v12) | 0 (0%) | 0 (0%) | **1 (10%)** | — | no | ❌ FULL deferred — gate failed (but +1 vs v11) |
| **Spider2-Lite — SF lane** | 207 | — | — | — | — | — | no | skipped |
| **Spider2-Lite — SQLite stub** | 135 | — | — | — | — | — | **YES** | non-comparable always |

## Aggregate Snow progression

| metric | v10 | v11 | v12 | **v13** |
|---|---:|---:|---:|---:|
| chosen_schema_valid | 0 | 1 | 0 | **0** |
| object_not_found AT engine | 7 | 0 | 0 | 0 |
| schema_invalid (validator gate) | n/a | 9 | 10 | 9 |
| repair_helpful | 0 | 0 | 0 | 0 |

## Aggregate BQ progression

| metric | v10 | v11 | **v12** |
|---|---:|---:|---:|
| chosen_schema_valid | n/a (no validator) | 0 | **1** ✅ |
| object_not_found AT engine | 10 | 0 | 0 |
| struct_field_skips (FP avoided) | n/a | n/a | **68** |
| wildcard_table_resolves | n/a | n/a | **19** |
| schema_invalid | n/a | 10 | 9 |
