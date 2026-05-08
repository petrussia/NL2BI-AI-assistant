# Spider2 v16 master matrix — Phase 16 snapshot

_Generated: 2026-05-08. **Two real benchmark numbers**: DBT FULL 68
(13.2%) + BQ v16 pilot10 schema_valid 60% (first non-DBT lane to
clear schema_valid gate)._

| benchmark | n_full | n_pilot v16 | parse_ok | execute_ok | schema_valid | task_success | non-comp | status |
|---|---:|---:|---:|---:|---:|---:|:---:|---|
| **Spider2-DBT v4** | 68 | — | — | — | — | **9 (13.2%)** | no | ✅ FULL DONE (Phase 11) |
| **Spider2-Lite — BQ lane** | 205 | 10 (v16) | 0 (0%) | 0 (0%) | **6 (60%)** ✅ | — | no | ❌ FULL deferred — parse_ok gate failed (catalog vs live divergence) |
| **Spider2-Snow canonical** | 547 | 10 (v16) | 0 (0%) | 0 (0%) | **0 (0%)** | — | no | ❌ FULL deferred — schema_valid gate failed |
| **Spider2-Lite — SF lane** | 207 | — | — | — | — | — | no | skipped (Snow gate) |
| **Spider2-Lite — SQLite stub** | 135 | — | — | — | — | — | **YES** | non-comparable always |

## BQ progression v10 → v11 → v12 → **v16**

| metric | v10 | v11 | v12 | **v16** |
|---|---:|---:|---:|---:|
| chosen_schema_valid | n/a | 0 | 1 | **6** ✅ |
| parse_ok | 0 | 0 | 0 | 0 |
| object_not_found AT engine | 10 | 0 | 0 | 5 (after schema gate) |
| schema_invalid (validator) | n/a | 10 | 9 | 4 |
| constrained_repair_helpful | n/a | n/a | n/a | **6** NEW |
| struct_field_skips | n/a | n/a | 68 | 65 |
| wildcard_resolves | n/a | n/a | 19 | 17 |

## Snow progression v10 → v11 → v12 → v13 → **v16**

| metric | v10 | v11 | v12 | v13 | **v16** |
|---|---:|---:|---:|---:|---:|
| chosen_schema_valid | 0 | **1** | 0 | 0 | **0** |
| object_not_found AT engine | 7 | 0 | 0 | 0 | 0 |
| schema_invalid | n/a | 9 | 10 | 9 | 10 |
| constrained_repair_helpful | n/a | 0 | 0 | 0 | 0 |
