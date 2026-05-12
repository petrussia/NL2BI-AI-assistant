# DBT ablation — V1 vs V2 vs V4

_Run: dbt_smoke_v26, generated 2026-05-10T19:51:26.465723+00:00_

## Per-variant aggregates

| variant | n | dbt_run_ok | matched | dbt_pass_total | dbt_err_total | wall_s_avg |
|---|---:|---:|---:|---:|---:|---:|
| v4 | 1 | 0/1 | 0/1 | 0 | 0 | 35.3 |

## Per-task

| iid | variant | dbt_run_rc | pass/err | score | apply | wall_s |
|---|---|---:|---|---|---|---:|
| asana001 | v4 | 1 | 0/0 | 0/1 (rate=0.0) | diff | 35.3 |