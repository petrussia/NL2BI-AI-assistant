# Spider2 v12 master matrix — Phase 14 snapshot

_Generated: 2026-05-08. **One real FULL** (DBT 68 = 13.2%). Three
gate-failed pilots this phase (BQ v11, Snow v11, Snow v12)._

| benchmark | n_full | n_pilot v12 | parse_ok | execute_ok | schema_valid | task_success | non-comp | status |
|---|---:|---:|---:|---:|---:|---:|:---:|---|
| **Spider2-DBT v4** | 68 | — | — | — | — | **9 (13.2%)** | no | ✅ FULL DONE (Phase 11) |
| **Spider2-Snow canonical** | 547 | 10 (v12) | 0 (0%) | 0 (0%) | **0 (0%)** | — | no | ❌ FULL deferred (gate ≥30% failed) |
| **Spider2-Lite — BQ lane** | 205 | 10 (v11) | 0 (0%) | 0 (0%) | **0 (0%)** | — | no | ❌ FULL deferred (gate ≥30% failed) |
| **Spider2-Lite — SF lane** | 207 | — | — | — | — | — | no | skipped (Snow gate failed) |
| **Spider2-Lite — SQLite stub** | 135 | — | — | — | — | — | **YES** | non-comparable always |

## v10 → v11 → v12 progression on Snow (same 10-task slice)

| metric | v10 | v11 | **v12** |
|---|---:|---:|---:|
| chosen_schema_valid | 0 | **1 (10%)** | **0 (0%)** ← regression |
| `object_not_found` AT engine | 7 | 0 | 0 |
| `schema_invalid` (validator) | n/a | 9 | 10 |
| `syntax` | 4 | 1 | 0 |
| repair_helpful | 0 | 0 | 0 |

## v10 → v11 BQ (same 10-task slice)

| metric | v10 | **v11** |
|---|---:|---:|
| chosen_schema_valid | n/a (no validator) | 0 |
| parse_ok / execute_ok | 0/0 | 0/0 |
| `object_not_found` AT engine | 10 | 0 |
| `schema_invalid` (validator) | n/a | 10 |
