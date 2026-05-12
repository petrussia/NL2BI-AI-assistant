# DBT ablation — V1 vs V2 vs V4

_Run: dbt_full_v26_final17, generated 2026-05-10T23:03:55.003166+00:00_

## Per-variant aggregates

| variant | n | dbt_run_ok | matched | dbt_pass_total | dbt_err_total | wall_s_avg |
|---|---:|---:|---:|---:|---:|---:|
| v4 | 17 | 6/17 | 1/17 | 291 | 53 | 44.0 |

## Per-task

| iid | variant | dbt_run_rc | pass/err | score | apply | wall_s |
|---|---|---:|---|---|---|---:|
| provider001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | fallback_sql | 68.8 |
| asana001 | v4 | 1 | 30/21 | 0/1 (rate=0.0) | diff | 38.4 |
| shopify001 | v4 | 0 | 85/3 | 0/1 (rate=0.0) | diff | 56.4 |
| asset001 | v4 | 0 | 0/0 | 0/1 (rate=0.0) | diff | 35.4 |
| flicks001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 29.7 |
| analytics_engineering001 | v4 | 0 | 2/0 | 0/1 (rate=0.0) | diff | 32.0 |
| xero_new001 | v4 | 1 | 16/0 | 0/1 (rate=0.0) | fallback_sql | 73.8 |
| chinook001 | v4 | 1 | 60/0 | 0/1 (rate=0.0) | diff | 48.0 |
| workday002 | v4 | 1 | 42/23 | 0/1 (rate=0.0) | diff | 38.1 |
| scd001 | v4 | 0 | 14/0 | 0/1 (rate=0.0) | diff | 31.2 |
| airport001 | v4 | 0 | 4/1 | 0/1 (rate=0.0) | diff | 27.9 |
| salesforce001 | v4 | 2 | 0/0 | 1/1 (rate=1.0) | diff | 29.8 |
| recharge001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | fallback_sql | 73.8 |
| maturity001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 33.4 |
| tpch002 | v4 | 1 | 0/5 | 0/1 (rate=0.0) | diff | 35.7 |
| nba001 | v4 | 0 | 38/0 | 0/1 (rate=0.0) | diff | 55.6 |
| quickbooks001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 40.0 |