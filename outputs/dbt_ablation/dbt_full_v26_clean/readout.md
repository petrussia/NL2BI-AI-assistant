# DBT ablation — V1 vs V2 vs V4

_Run: dbt_full_v26_clean, generated 2026-05-10T23:59:27.123391+00:00_

## Per-variant aggregates

| variant | n | dbt_run_ok | matched | dbt_pass_total | dbt_err_total | wall_s_avg |
|---|---:|---:|---:|---:|---:|---:|
| v4 | 68 | 26/68 | 9/68 | 1220 | 259 | 42.6 |

## Per-task

| iid | variant | dbt_run_rc | pass/err | score | apply | wall_s |
|---|---|---:|---|---|---|---:|
| playbook001 | v4 | 0 | 0/0 | 1/1 (rate=1.0) | diff | 33.7 |
| provider001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | fallback_sql | 68.3 |
| asana001 | v4 | 1 | 30/21 | 0/1 (rate=0.0) | diff | 38.2 |
| shopify001 | v4 | 0 | 85/3 | 0/1 (rate=0.0) | diff | 54.0 |
| asset001 | v4 | 0 | 0/0 | 0/1 (rate=0.0) | diff | 35.3 |
| flicks001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 29.6 |
| analytics_engineering001 | v4 | 0 | 2/0 | 0/1 (rate=0.0) | diff | 31.7 |
| xero_new001 | v4 | 1 | 16/0 | 0/1 (rate=0.0) | fallback_sql | 71.8 |
| chinook001 | v4 | 1 | 60/0 | 0/1 (rate=0.0) | diff | 46.9 |
| f1001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 35.5 |
| netflix001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 27.4 |
| workday002 | v4 | 1 | 42/23 | 0/1 (rate=0.0) | diff | 37.2 |
| pendo001 | v4 | 0 | 42/0 | 0/1 (rate=0.0) | diff | 40.3 |
| synthea001 | v4 | 1 | 0/128 | 0/1 (rate=0.0) | diff | 32.2 |
| inzight001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 36.0 |
| google_play001 | v4 | 0 | 19/0 | 0/1 (rate=0.0) | diff | 44.8 |
| airbnb002 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 37.3 |
| biketheft001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 29.8 |
| tickit002 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | fallback_sql | 66.6 |
| activity001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 25.4 |
| scd001 | v4 | 0 | 14/0 | 0/1 (rate=0.0) | diff | 31.7 |
| lever001 | v4 | 0 | 58/0 | 1/1 (rate=1.0) | diff | 41.3 |
| greenhouse001 | v4 | 1 | 74/0 | 0/1 (rate=0.0) | diff | 39.7 |
| app_reporting002 | v4 | 0 | 46/0 | 0/1 (rate=0.0) | diff | 40.5 |
| mrr001 | v4 | 1 | 28/2 | 1/1 (rate=1.0) | diff | 33.4 |
| xero001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 28.2 |
| movie_recomm001 | v4 | 0 | 0/13 | 0/1 (rate=0.0) | diff | 34.0 |
| quickbooks003 | v4 | 1 | 71/0 | 1/1 (rate=1.0) | diff | 44.3 |
| qualtrics001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | fallback_sql | 69.0 |
| recharge002 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 43.2 |
| atp_tour001 | v4 | 1 | 0/8 | 0/1 (rate=0.0) | fallback_sql | 71.7 |
| quickbooks002 | v4 | 1 | 67/0 | 0/1 (rate=0.0) | diff | 50.0 |
| google_ads001 | v4 | 0 | 33/0 | 0/1 (rate=0.0) | diff | 36.5 |
| airport001 | v4 | 0 | 4/1 | 0/1 (rate=0.0) | diff | 27.8 |
| tpch001 | v4 | 0 | 0/0 | 0/1 (rate=0.0) | diff | 36.1 |
| salesforce001 | v4 | 2 | 0/0 | 1/1 (rate=1.0) | diff | 28.9 |
| hubspot001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | fallback_sql | 70.2 |
| shopify002 | v4 | 0 | 85/3 | 0/1 (rate=0.0) | diff | 53.3 |
| social_media001 | v4 | 1 | 44/1 | 0/1 (rate=0.0) | diff | 44.6 |
| xero_new002 | v4 | 0 | 16/0 | 0/1 (rate=0.0) | diff | 34.5 |
| divvy001 | v4 | 2 | 0/0 | -/- (rate=-) | diff | 205.2 |
| playbook002 | v4 | 0 | 0/0 | 0/1 (rate=0.0) | diff | 29.6 |
| apple_store001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 32.6 |
| jira001 | v4 | 0 | 61/0 | 0/1 (rate=0.0) | diff | 42.8 |
| zuora001 | v4 | 1 | 31/9 | 0/1 (rate=0.0) | diff | 34.6 |
| superstore001 | v4 | 0 | 4/0 | 1/1 (rate=1.0) | diff | 35.2 |
| marketo001 | v4 | 0 | 48/0 | 0/1 (rate=0.0) | diff | 44.2 |
| f1002 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 33.7 |
| gitcoin001 | v4 | 1 | 0/10 | 0/1 (rate=0.0) | diff | 32.2 |
| shopify_holistic_reporting001 | v4 | 1 | 99/25 | 0/1 (rate=0.0) | diff | 49.7 |
| hive001 | v4 | 0 | 1/1 | 0/1 (rate=0.0) | diff | 32.5 |
| workday001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 30.4 |
| f1003 | v4 | 2 | 0/0 | 1/1 (rate=1.0) | diff | 27.1 |
| retail001 | v4 | 2 | 0/0 | 1/1 (rate=1.0) | diff | 26.5 |
| google_play002 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 30.3 |
| sap001 | v4 | 1 | 19/6 | 0/1 (rate=0.0) | diff | 39.5 |
| airbnb001 | v4 | 0 | 14/0 | 0/1 (rate=0.0) | diff | 49.8 |
| app_reporting001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 36.4 |
| mrr002 | v4 | 0 | 17/0 | 1/1 (rate=1.0) | diff | 29.8 |
| twilio001 | v4 | 0 | 24/0 | 0/1 (rate=0.0) | diff | 33.5 |
| intercom001 | v4 | 0 | 28/0 | 0/1 (rate=0.0) | diff | 39.6 |
| tickit001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 35.3 |
| reddit001 | v4 | 0 | 0/0 | 0/1 (rate=0.0) | diff | 28.7 |
| recharge001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | fallback_sql | 71.3 |
| maturity001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 32.7 |
| tpch002 | v4 | 1 | 0/5 | 0/1 (rate=0.0) | diff | 36.5 |
| nba001 | v4 | 0 | 38/0 | 0/1 (rate=0.0) | diff | 54.9 |
| quickbooks001 | v4 | 2 | 0/0 | 0/1 (rate=0.0) | diff | 40.9 |