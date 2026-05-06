# DBT ablation — V1 vs V2 vs V4

_Run: ablation_main, generated 2026-05-06T17:19:26.279388+00:00_

## Per-variant aggregates

| variant | n | dbt_run_ok | matched | dbt_pass_total | dbt_err_total | wall_s_avg |
|---|---:|---:|---:|---:|---:|---:|
| v1 | 6 | 0/6 | 2/6 | 0 | 0 | 45.3 |
| v2 | 6 | 0/6 | 2/6 | 0 | 0 | 45.5 |
| v4 | 6 | 2/6 | 3/6 | 88 | 21 | 46.0 |

## Per-task

| iid | variant | dbt_run_rc | pass/err | score | apply | wall_s |
|---|---|---:|---|---|---|---:|
| asana001 | v1 | 2 | 0/0 | 0/1 (rate=0.0) | sql_file | 62.8 |
| asana001 | v2 | 2 | 0/0 | 0/1 (rate=0.0) | sql_file | 56.3 |
| asana001 | v4 | 1 | 30/21 | -/- (rate=-) | diff | 40.2 |
| playbook001 | v1 | 1 | 0/0 | 1/1 (rate=1.0) | sql_file | 43.0 |
| playbook001 | v2 | 2 | 0/0 | 1/1 (rate=1.0) | sql_file | 40.3 |
| playbook001 | v4 | 0 | 0/0 | 1/1 (rate=1.0) | diff | 42.8 |
| retail001 | v1 | 2 | 0/0 | 1/1 (rate=1.0) | sql_file | 29.8 |
| retail001 | v2 | 2 | 0/0 | 1/1 (rate=1.0) | sql_file | 25.5 |
| retail001 | v4 | 2 | 0/0 | 1/1 (rate=1.0) | diff | 29.3 |
| recharge002 | v1 | 2 | 0/0 | 0/1 (rate=0.0) | sql_file | 41.0 |
| recharge002 | v2 | 2 | 0/0 | 0/1 (rate=0.0) | sql_file | 47.9 |
| recharge002 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 76.4 |
| xero001 | v1 | 2 | 0/0 | 0/1 (rate=0.0) | sql_file | 47.7 |
| xero001 | v2 | 2 | 0/0 | 0/1 (rate=0.0) | sql_file | 34.3 |
| xero001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 34.9 |
| lever001 | v1 | 2 | 0/0 | 0/1 (rate=0.0) | sql_file | 47.4 |
| lever001 | v2 | 2 | 0/0 | 0/1 (rate=0.0) | sql_file | 68.5 |
| lever001 | v4 | 0 | 58/0 | 1/1 (rate=1.0) | diff | 52.2 |