# DBT ablation — V1 vs V2 vs V4

_Run: dbt_full_diagnostic_v23, generated 2026-05-10T04:49:39.030090+00:00_

## Per-variant aggregates

| variant | n | dbt_run_ok | matched | dbt_pass_total | dbt_err_total | wall_s_avg |
|---|---:|---:|---:|---:|---:|---:|
| v4 | 67 | 0/67 | 0/67 | 0 | 0 | 64.5 |

## Per-task

| iid | variant | dbt_run_rc | pass/err | score | apply | wall_s |
|---|---|---:|---|---|---|---:|
| playbook001 | v4 | None | 0/0 | -/- (rate=-) | - | 3.8 |
| provider001 | v4 | None | 0/0 | -/- (rate=-) | - | 15.1 |
| asana001 | v4 | None | 0/0 | -/- (rate=-) | - | 14.8 |
| shopify001 | v4 | None | 0/0 | -/- (rate=-) | - | 18.2 |
| asset001 | v4 | None | 0/0 | -/- (rate=-) | - | 17.8 |
| flicks001 | v4 | None | 0/0 | -/- (rate=-) | - | 24.1 |
| analytics_engineering001 | v4 | None | 0/0 | -/- (rate=-) | - | 5.6 |
| xero_new001 | v4 | None | 0/0 | -/- (rate=-) | - | 7.4 |
| chinook001 | v4 | None | 0/0 | -/- (rate=-) | - | 7.1 |
| f1001 | v4 | None | 0/0 | -/- (rate=-) | - | 10.8 |
| netflix001 | v4 | None | 0/0 | -/- (rate=-) | - | 8.7 |
| workday002 | v4 | None | 0/0 | -/- (rate=-) | - | 8.7 |
| pendo001 | v4 | None | 0/0 | -/- (rate=-) | - | 10.2 |
| synthea001 | v4 | None | 0/0 | -/- (rate=-) | - | 8.5 |
| inzight001 | v4 | None | 0/0 | -/- (rate=-) | - | 4.5 |
| google_play001 | v4 | None | 0/0 | -/- (rate=-) | - | 4.6 |
| airbnb002 | v4 | None | 0/0 | -/- (rate=-) | - | 4.3 |
| biketheft001 | v4 | None | 0/0 | -/- (rate=-) | - | 4.3 |
| tickit002 | v4 | None | 0/0 | -/- (rate=-) | - | 4.2 |
| activity001 | v4 | None | 0/0 | -/- (rate=-) | - | 4.1 |
| scd001 | v4 | None | 0/0 | -/- (rate=-) | - | 7.7 |
| lever001 | v4 | None | 0/0 | -/- (rate=-) | - | 4.4 |
| greenhouse001 | v4 | None | 0/0 | -/- (rate=-) | - | 4.4 |
| app_reporting002 | v4 | None | 0/0 | -/- (rate=-) | - | 8.4 |
| mrr001 | v4 | None | 0/0 | -/- (rate=-) | - | 10.1 |
| xero001 | v4 | None | 0/0 | -/- (rate=-) | - | 11.4 |
| movie_recomm001 | v4 | None | 0/0 | -/- (rate=-) | - | 10.1 |
| quickbooks003 | v4 | None | 0/0 | -/- (rate=-) | - | 4.1 |
| qualtrics001 | v4 | None | 0/0 | -/- (rate=-) | - | 4.1 |
| recharge002 | v4 | None | 0/0 | -/- (rate=-) | - | 4.4 |
| atp_tour001 | v4 | None | 0/0 | -/- (rate=-) | - | 4.3 |
| quickbooks002 | v4 | None | 0/0 | -/- (rate=-) | - | 4.2 |
| google_ads001 | v4 | None | 0/0 | -/- (rate=-) | - | 4.0 |
| airport001 | v4 | None | 0/0 | -/- (rate=-) | - | 20.9 |
| tpch001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.2 |
| salesforce001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| hubspot001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| shopify002 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| social_media001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| xero_new002 | v4 | None | 0/0 | -/- (rate=-) | - | 126.1 |
| divvy001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.8 |
| playbook002 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| apple_store001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.2 |
| jira001 | v4 | None | 0/0 | -/- (rate=-) | - | 0.7 |
| zuora001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.0 |
| superstore001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.0 |
| marketo001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.3 |
| f1002 | v4 | None | 0/0 | -/- (rate=-) | - | 126.0 |
| gitcoin001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| shopify_holistic_reporting001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.2 |
| hive001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| workday001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.1 |
| f1003 | v4 | None | 0/0 | -/- (rate=-) | - | 126.5 |
| retail001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.3 |
| google_play002 | v4 | None | 0/0 | -/- (rate=-) | - | 126.1 |
| sap001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.0 |
| airbnb001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.0 |
| app_reporting001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.0 |
| mrr002 | v4 | None | 0/0 | -/- (rate=-) | - | 126.0 |
| twilio001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.3 |
| intercom001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| tickit001 | v4 | None | 0/0 | -/- (rate=-) | - | 126.0 |
| reddit001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| recharge001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| maturity001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| tpch002 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 |
| nba001 | v4 | None | 0/0 | -/- (rate=-) | - | 125.9 | |