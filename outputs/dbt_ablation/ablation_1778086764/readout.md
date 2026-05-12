# DBT ablation — V1 vs V2 vs V4

_Run: ablation_1778086764, generated 2026-05-06T17:04:14.874448+00:00_

## Per-variant aggregates

| variant | n | dbt_run_ok | matched | dbt_pass_total | dbt_err_total | wall_s_avg |
|---|---:|---:|---:|---:|---:|---:|
| v1 | 2 | 0/2 | 0/2 | 0 | 0 | 53.2 |
| v2 | 2 | 0/2 | 0/2 | 0 | 0 | 47.2 |
| v4 | 2 | 1/2 | 0/2 | 30 | 21 | 41.7 |

## Per-task

| iid | variant | dbt_run_rc | pass/err | score | apply | wall_s |
|---|---|---:|---|---|---|---:|
| asana001 | v1 | 2 | 0/0 | -/- (rate=-) | sql_file | 64.6 |
| asana001 | v2 | 2 | 0/0 | -/- (rate=-) | sql_file | 55.8 |
| asana001 | v4 | 1 | 30/21 | -/- (rate=-) | diff | 41.3 |
| playbook001 | v1 | 1 | 0/0 | -/- (rate=-) | sql_file | 41.9 |
| playbook001 | v2 | 2 | 0/0 | -/- (rate=-) | sql_file | 38.7 |
| playbook001 | v4 | 0 | 0/0 | -/- (rate=-) | diff | 42.1 |