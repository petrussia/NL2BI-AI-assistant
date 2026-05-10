# Spider2 FULL diagnostic master matrix — v23

| benchmark | lane | run_id | n_total | n_completed | n_failed_runtime | schema_valid | parse_ok | exec_ok | task_success | official-comparable | diagnostic-only | wall_sec | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|
| lite | bq | `lite_full_diagnostic_v23_bq` | 205 | 14 | 8 | 28.6% | 42.9% | 14.3% | NA | NO | YES | 731 | partial 14/205 — OOM under concurrency |
| lite | sf | `lite_full_diagnostic_v23_snow` | 207 | 70 | 70 | 0.0% | 0.0% | NA | NA | NO | YES | 900 | CANCELLED — 15 OOM + 55 stub-aborted |
| lite | sqlite | n/a | 135 | 0 | 0 | NA | NA | NA | NA | NO | NO | 0 | non-comparable; not run |
| snow | sf | `snow_full_diagnostic_v23` | 547 | 32 | 32 | 0.0% | 0.0% | NA | NA | NO | YES | 407 | CANCELLED — 32/32 OOM |
| dbt | dbt | `dbt_full_diagnostic_v23` | 68 | 0 | 0 | NA | NA | NA | NA | NO | YES | 0 | BLOCKED — CUBLAS_ALLOC_FAILED |
| **prior baselines (for context)** | | | | | | | | | | | | | |
| lite | bq | `lite_bq_v22_pilot50` (Phase 22) | 50 | 50 | 0 | 54.0% | 98.0% | 44.0% | NA | NO (pilot, not FULL) | YES | 3600 | gates not cleared (sv ≥ 60%? no; exec ≥ 50%? no) |
| dbt | dbt | Phase11 baseline | 68 | 68 | — | — | — | — | **13.2%** | **YES** | NO | — | only publishable Spider2 number |

## Key takeaways

- **Phase 23 produced no new official-comparable benchmark numbers.**
  All four FULL diagnostic runs are partial or cancelled.
- The **only publishable Spider2 number remains 9/68 = 13.2 %** task
  success on DBT (Phase 11 baseline). This is unchanged.
- The 14-task BQ partial sample is too small for a publishable claim
  but is directionally consistent with v22 pilot50.
- Re-launch path requires (a) GPU lock pre-installed before any BG
  thread starts, (b) Snow connector creds for execute_ok / explain_ok,
  (c) sequential / non-overlapping runs.
