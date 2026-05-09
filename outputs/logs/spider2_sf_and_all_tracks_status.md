# Spider2 SF + all tracks — status

_Produced at the close of the session that wired the SF executor +
schema index + prompting + agent + readiness-gated runner, plus the
Spider2-DBT official evaluator wrapper._

## 1. Snowflake connection status

✅ Connection works.
- `CURRENT_USER()` = `SPIDER2_BENCH`
- `CURRENT_ROLE()` = `SPIDER2_RW`
- `CURRENT_WAREHOUSE()` = `SPIDER2_WH` (X-Small, AUTO_SUSPEND 60s)
- `CURRENT_DATABASE()` / `CURRENT_SCHEMA()` = `SPIDER2_WORK` / `PUBLIC`
- `CURRENT_VERSION()` = `10.16.101`

## 2. Account region / cloud / self-host eligibility

- Account identifier: **`QOBJWEZ.DI69621`**
- Cloud: **AWS**
- Region: **`ap-south-1` (Mumbai)**
- Spider2 self-host share is published only to AWS `us-west-2`, so
  **self-host on this account is NOT eligible**.
- Plan: try Marketplace share first (cross-region OK with xlang-ai
  approval); fall back to creating a new us-west-2 account if
  necessary. Full plan + email template + SQL: [outputs/logs/spider2_sf_self_host_plan.md](spider2_sf_self_host_plan.md).

## 3. Visible databases

| Name | Origin | Kind |
|---|---|---|
| `SNOWFLAKE` | `SNOWFLAKE.ACCOUNT_USAGE` | APPLICATION |
| `SNOWFLAKE_SAMPLE_DATA` | `SFSALESSHARED.SFC_SAMPLES_AWSAPSOUTH1.SAMPLE_DATA` | IMPORTED DATABASE |
| `SPIDER2_WORK` | (own) | STANDARD |

## 4. Required databases for Spider2-Lite SF

58 (from local `resource/databases/snowflake/`): `AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET`, `AUSTIN`, `BRAZE_USER_EVENT_DEMO_DATASET`, `CENSUS_BUREAU_ACS_2`, …, `CRYPTO`, `DEPS_DEV_V1`, `ETHEREUM_BLOCKCHAIN`, …, `PATENTS`, …

Full list: [outputs/snowflake/readiness/databases_visible.json](../snowflake/readiness/databases_visible.json) (`missing_databases` field).

## 5. Missing databases

**58 of 58 missing.** Including `PATENTS` (the very first SF item, `sf_bq029`, depends on it).

## 6. Is PATENTS visible?

❌ No.

## 7. Can real Spider2-Lite SF benchmark run now?

❌ No. `can_execute_real_sql=False, reason="58 required databases not visible …"`.

The SF runner is already gated on this readiness check:
```bash
python snowflake_setup/run_spider2_lite_sf_agent.py --limit 10 --execute true
```
correctly refuses to issue queries and writes `mode=blocked_missing_snowflake_database` per item.

## 8. Exact blocker + path forward

Run [outputs/logs/spider2_sf_self_host_plan.md](spider2_sf_self_host_plan.md). Summary:
- Path A (recommended): submit the Spider2 access form with
  `QOBJWEZ.DI69621` / `ap-south-1`, ask for cross-region Marketplace
  share. Wait for shares; verify with `probe_databases.py`.
- Path B (fallback): create a new account in AWS `us-west-2`, run
  `friend_provisioning.sql`, accept share, run
  `spider2-data-share` migration scripts, update `.env`.

## 9. Code added for SF executor / schema / prompting / agent / readiness

| Module | Purpose |
|---|---|
| `repo/src/evaluation/spider2_sf_readiness_v8.py` | SfReadiness dataclass + `check_readiness(required_dbs)` |
| `repo/src/evaluation/spider2_sf_executor_v8.py` | `build_sf_executor(...)` mirroring BQ executor contract; `EXPLAIN USING TEXT` for free dry_run; full SF error taxonomy |
| `repo/src/evaluation/spider2_sf_schema_index_v8.py` | Local-metadata first; `build_index_via_executor` fallback; cache to `outputs/cache/spider2_sf_schema_index_v8/` |
| `repo/src/evaluation/spider2_sf_prompting_v8.py` | `direct_prompt`, `retrieval_prompt`, `cte_prompt`, `repair_prompt` + Snowflake dialect rules |
| `repo/src/evaluation/spider2_sf_agent_v8.py` | Single-shot multi-candidate (C0/C1/C2/C3-repaired) over SF executor |
| `snowflake_setup/run_spider2_lite_sf_agent.py` | Readiness-gated runner; refuses to issue queries when `can_execute_real_sql=False` |
| `snowflake_setup/probe_databases.py` | Improved probe writing `outputs/snowflake/readiness/databases_visible.{json,md}` |

## 10. Spider2-Lite SF limit=1/3/10 status

All three already ran in this session:

| Limit | Run dir | Rows written | Blocked |
|---|---|---:|---:|
| 1 | `outputs/snowflake/runs/sf_limit1_*/` | 1 | 1 |
| 3 | `outputs/snowflake/runs/sf_limit3_*/` | 3 | 3 |
| 10 | `outputs/snowflake/runs/sf_limit10_*/` (with `--execute true`) | 10 | 10 |

All blocked correctly because `PATENTS` (and the other 57 expected dbs)
are not attached. No SF queries were issued.

## 11. Spider2-Snow readiness

Same blocker as Spider2-Lite SF. The SF executor/schema/prompting/agent
modules will be reused 1-to-1 once shares land. No code change
required to add a `--benchmark spider2-snow` runner; just point at the
`spider2-snow.jsonl` task list.

## 12. Spider2-DBT official evaluator status

✅ Wired and verified on `asana001`:
- `spider2_dbt_bridge/server_side/server_official_eval.py` deployed to
  `/home/denis/dbt/colab_bridge/server_official_eval.py`.
- Builds per-task `result_dir/` with `results_metadata.jsonl` +
  produced `.duckdb`, invokes upstream `evaluate.py`, parses
  `rate / matched / total`, updates the task's `result.json`.
- Smoke result: `eval_status=ok, official_score={rate:0.0, matched:0,
  total:1}, official_eval_rc=0`. Smoke SQL didn't match gold (expected).

## 13. Commands for the next safe runs

### Snowflake
```bash
# Re-check share status after xlang-ai grants Marketplace share:
python snowflake_setup/probe_databases.py

# Once dbs attached, ramp up A_sf:
python snowflake_setup/run_spider2_lite_sf_agent.py --limit 1 --execute true
python snowflake_setup/run_spider2_lite_sf_agent.py --limit 3 --execute true
python snowflake_setup/run_spider2_lite_sf_agent.py --limit 10 --execute true
```

### Spider2-DBT (full per-task with official eval)
```bash
TASK_ID=playbook001  # or any of the 68
python spider2_dbt_bridge/run_one_task_pipeline.py --task-id $TASK_ID --mode manual
ssh denis@103.54.18.91 "/home/denis/dbt/.venv/bin/python /home/denis/dbt/colab_bridge/server_official_eval.py --task-id $TASK_ID --write-result"
python spider2_dbt_bridge/collect_remote_result.py --task-id $TASK_ID
cat data/spider2_dbt/tasks/$TASK_ID/result/result.json
```

### Spider2-Lite BQ (already done; commit `54e060c`)
No new run needed. EX = 2.45% / exec_ok = 45.4%. Future
question-understanding work would lift further.

## 14. Git status summary

Working tree has many pre-existing untracked files from prior phases.
This PR adds:
- 6 new modules under `repo/src/evaluation/spider2_sf_*_v8.py` and `spider2_sf_agent_v8.py`
- 2 new `snowflake_setup/` scripts (`probe_databases.py`, `run_spider2_lite_sf_agent.py`)
- 1 new server-side script `spider2_dbt_bridge/server_side/server_official_eval.py`
- Reports: `outputs/logs/spider2_sf_self_host_plan.md`,
  `outputs/REPORT_ALL_SPIDER2_TRACKS.md`,
  this status file
- Readiness snapshot: `outputs/snowflake/readiness/databases_visible.{json,md}`
- 3 SF runs (selection-only): `outputs/snowflake/runs/sf_limit{1,3,10}_*/`

`.env` and any secret files remain `.gitignore`'d.

## 15. Commit SHA

To be filled after commit.
