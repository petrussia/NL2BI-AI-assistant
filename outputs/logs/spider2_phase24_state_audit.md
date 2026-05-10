# Phase 24 — STAGE 0 state audit

_Generated: 2026-05-10 | branch: `experiments/denis` | parent commit: `5f6a39b` (Phase 23)_

## 1. Git

| field | value |
|---|---|
| HEAD | `5f6a39b` Phase 23 Spider2 FULL diagnostic |
| Parent | `1ba0b8f` Phase 22 |
| Branch | `experiments/denis` |
| Phase 23 artifacts present locally | YES (REPORT, master matrix, runs/lite_full_diagnostic_v23_bq) |

## 2. Bridge / GPU

| field | value |
|---|---|
| `/health` | OK pid 3960 |
| URL | `https://corpus-vatican-technical-pennsylvania.trycloudflare.com` |
| GPU free | **6.13 GB** of 79.25 GB |
| GPU allocated | 71.27 GB (planner 30B + emitter 7B both loaded) |
| Models | `Qwen/Qwen3-Coder-30B-A3B-Instruct` (planner) + `Qwen/Qwen2.5-Coder-7B-Instruct` (emitter) |

## 3. Phase 23 BG runs — final state

| run_id | n_processed | done | cancelled | err_top |
|---|---:|:-:|:-:|---|
| `lite_full_diagnostic_v23_bq` | 14 / 205 | no | **YES (Phase 24 force-cancel)** | OOM 8, bq_dry_run_failed 3, schema_invalid 2 |
| `snow_full_diagnostic_v23` | 170 / 547 | no | YES | RuntimeError 138 (stub-abort), OOM 32 |
| `lite_full_diagnostic_v23_snow` | 207 / 207 | yes | yes | RuntimeError 192 (stub-abort), OOM 15 |

Lite-Snow drained fully via stub-abort. Snow Spider2 partially drained.
Lite-BQ FULL force-cancelled in Phase 24.

## 4. Threads still alive on bridge

`Thread-632 (_runner)` and `Thread-640 (_runner)` still alive. After
STAGE 2 cleanup, all v23 generator helpers (`_v18_plan`,
`_v18_plan_local`, `_gen`, `_gen_planner`, `_gen_planner_local`,
`_gen_emitter`, `_gen_emitter_local`) replaced by fast-fail
stubs. Threads will exit on their next loop iteration (no further
GPU contention).

## 5. Engine auth

| engine | status |
|---|---|
| BigQuery | OK (`project-0e0fc8a5-27b1-4e00-912`, dry_run probe 0 bytes) |
| Snowflake | **BLOCKED** (env vars unset; user action required to fix) — **Snow NOT run in Phase 24** |
| DBT remote | OK at `denis@103.54.18.91`/`/home/denis/dbt/.venv/bin/dbt` — **DBT NOT run in Phase 24** |

## 6. Datasets / catalogs (unchanged from Phase 23)

| dataset / cache | rows |
|---|---:|
| `spider2-lite.jsonl` | 547 |
| `spider2-snow.jsonl` | 547 |
| `data/spider2_dbt/tasks/` | 68 |
| `spider2_bq_live_catalog_v18.jsonl` | 428,424 |
| `spider2_snow_live_catalog_v18.jsonl` | 586,472 |

## 7. Lock dir

`outputs/runtime/` does not yet exist on Drive. STAGE 1 will create it
+ enforce a single-writer lock there.

## 8. Phase 24 plan

1. STAGE 1: build `gpu_lock_v24.py` (file-based exclusive lock on Drive)
   + `tools/run_spider2_sequential_v24.py` orchestrator that:
   - acquires lock
   - runs ONE benchmark / ONE BG thread max
   - releases lock on _DONE / _FAILED
2. STAGE 3: `bigquery_engine_compat_v24.py` — 6 rewrite rules.
3. STAGE 4: Lite-BQ pilot50 with rewrites; gate target sv ≥ 60% / exec_ok ≥ 50%.
4. STAGE 5: ONLY if gate cleared, run Lite-BQ FULL 205.
5. STAGE 6/7: report + commit local.
