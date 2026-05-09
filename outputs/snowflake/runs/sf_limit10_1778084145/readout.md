# Run sf_limit10_1778084145

_Generated: 2026-05-06T16:16:00.834325+00:00_

- benchmark: `spider2-lite`
- engine: `snowflake`
- limit: 10
- inference: `manual`
- execute flag: `true`
- will_execute: **False**

## Readiness

- connection_ok: True
- role_ok: True
- warehouse_ok: True
- can_execute_real_sql: **False**
- reason: `1 required databases not visible (first missing: ['PATENTS'])`
- visible dbs: 3; required: 1; missing: 1
- self_host_eligible: False (cloud=AWS region=ap-south-1)

## Selected items

| instance_id | db | mode |
|---|---|---|
| `sf_bq029` | `PATENTS` | blocked_missing_snowflake_database |
| `sf_bq026` | `PATENTS` | blocked_missing_snowflake_database |
| `sf_bq091` | `PATENTS` | blocked_missing_snowflake_database |
| `sf_bq099` | `PATENTS` | blocked_missing_snowflake_database |
| `sf_bq033` | `PATENTS` | blocked_missing_snowflake_database |
| `sf_bq209` | `PATENTS` | blocked_missing_snowflake_database |
| `sf_bq027` | `PATENTS` | blocked_missing_snowflake_database |
| `sf_bq210` | `PATENTS` | blocked_missing_snowflake_database |
| `sf_bq211` | `PATENTS` | blocked_missing_snowflake_database |
| `sf_bq213` | `PATENTS` | blocked_missing_snowflake_database |

## Next step
Real Spider2-Lite SF execution requires the missing databases. See `outputs/logs/spider2_sf_self_host_plan.md` for the Marketplace-share / self-host plan. Until then this runner records `blocked_missing_snowflake_database` per item.
