# Spider2 v9 master matrix — Phase 11 snapshot

_Generated: 2026-05-08. **One real FULL** (DBT 68, 13.2%). Two gate-failed FULL deferred (Snow 547, Lite 547)._

| benchmark | n_full | n_pilot | parse_ok pilot | task_success | non-comparable | status |
|---|---:|---:|---:|---:|:---:|---|
| **Spider2-DBT v4** | 68 | 68 | — | **9 (13.2%)** | no | ✅ FULL DONE |
| **Spider2-Snow canonical** | 547 | 10 | 0 (0.0%) | — | no | ❌ FULL deferred (gate ≥50% failed) |
| **Spider2-Lite — BQ lane** | 205 | 4 | 0 (0.0%) | — | no | ❌ FULL deferred (gate ≥30% failed) |
| **Spider2-Lite — SF lane** | 207 | 3 | 0 (0.0%) | — | no | ❌ FULL deferred (gate ≥30% failed) |
| **Spider2-Lite — SQLite stub** | 135 | 3 | 0 (0.0%) | — | **YES** | ❌ FULL deferred / non-comparable always |

> Do **not** average across rows. Each is a separate benchmark with a
> different evaluation contract.
> Spider2-Snow uses the **canonical 547** dataset (`xlang-ai/Spider2`,
> SHA in `external_benchmarks/spider2_snow/manifests/...`), NOT the 207
> sf-prefix subset of Spider2-Lite.
