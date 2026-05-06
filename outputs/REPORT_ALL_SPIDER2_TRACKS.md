# Unified Spider2 status — all tracks

_Snapshot of every Spider2 lane in the repo, what works today, and the
exact next-step command for each. Branch `experiments/denis`._

| Track | Status | Items | Real EX | Last command |
|---|---|---:|---|---|
| **Spider2-Lite BigQuery** | ✅ executed | 205 | **2.45%** (5/204), v7→v8 +0.49 pp | `tools/remote_scripts/129_spider2_bq_v8_runner.py` (Phase 10, commit `54e060c`) |
| **Spider2-Lite Snowflake** | ⚠ blocked, gated | 207 | n/a (0/58 dbs visible) | `python snowflake_setup/run_spider2_lite_sf_agent.py --limit 1` |
| **Spider2-Lite SQLite** | ✅ executed | 135 | non-comparable on sample | Phase 9, commit `0f70a5c` (`spider2lite_agent_v7_full_predictions.jsonl`, B_sqlite lane) |
| **Spider2-Snow** | ⏸ deferred | ~547 | requires SF dbs | n/a (waits on Spider2-Lite SF unblock) |
| **Spider2-DBT** | ✅ bridge + eval wired | 68 | dry-run on asana001 (smoke score 0/1) | `python spider2_dbt_bridge/run_one_task_pipeline.py --task-id asana001 --mode manual` then `server_official_eval.py` |

## Spider2-Lite BigQuery (A_bq lane)

- **Status:** end-to-end run completed; metrics in [outputs/REPORT_SPIDER2_V8.md](REPORT_SPIDER2_V8.md).
- **Headline:** v8 vs v7 — exec_ok 20.5% → **45.4%** (+24.9 pp); EX vs gold 1.96% → 2.45% (paired McNemar tied, helpful=2 / harmful=1).
- **Cost:** 10.91 GB BQ scanned ≈ $0.05 with `maximum_bytes_billed=10**9` per query.
- **Remaining gap:** ~88 items now BQ-execute but rows mismatch gold — reasoning, not grounding. Next levers: question rewrite, multi-step ReAct, oracle-tables analysis.

## Spider2-Lite Snowflake (A_sf lane)

- **Account:** `QOBJWEZ.DI69621`, AWS `ap-south-1` (Mumbai).
- **Connection:** ✅ ([outputs/snowflake/readiness/databases_visible.json](snowflake/readiness/databases_visible.json)).
- **Visible databases:** 3 (`SNOWFLAKE`, `SNOWFLAKE_SAMPLE_DATA`, `SPIDER2_WORK`).
- **Required:** 58 (`PATENTS`, `CRYPTO`, `AUSTIN`, … from local Spider2 metadata).
- **Missing:** **58 / 58** including `PATENTS` (the first SF item's database).
- **Self-host eligible:** **No** — Spider2 self-host share `SDB71929.SHARE_FOR_SPIDER2_DB` is published only to AWS `us-west-2` accounts. Two paths in [outputs/logs/spider2_sf_self_host_plan.md](logs/spider2_sf_self_host_plan.md):
  - Path A — Marketplace share (cross-region, lower friction): submit the
    Spider2 access form with `QOBJWEZ.DI69621`, request cross-region
    sharing.
  - Path B — Self-host: create a NEW SF account in `us-west-2`, run
    `friend_provisioning.sql`, accept share, run `spider2-data-share`
    migration scripts.

### What's wired (works today, gated on readiness)

- `repo/src/evaluation/spider2_sf_readiness_v8.py` — SfReadiness dataclass + `check_readiness(required_dbs)`.
- `repo/src/evaluation/spider2_sf_executor_v8.py` — `build_sf_executor(...)` matching the BQ executor contract; `EXPLAIN USING TEXT` for free dry_run; full error taxonomy (database_missing / object_not_found / permission_denied / warehouse_error / auth_error / timeout / syntax / unknown).
- `repo/src/evaluation/spider2_sf_schema_index_v8.py` — local metadata + executor fallback.
- `repo/src/evaluation/spider2_sf_prompting_v8.py` — Snowflake dialect rules (DATEDIFF arg order, FLATTEN, TRY_CAST, no `_TABLE_SUFFIX`, `ILIKE`, `QUALIFY`, VARIANT/OBJECT/ARRAY).
- `repo/src/evaluation/spider2_sf_agent_v8.py` — multi-candidate agent (C0/C1/C2/C3-repaired), single-shot.
- `snowflake_setup/run_spider2_lite_sf_agent.py` — readiness-gated runner.

### Default flow (today)

```bash
# Selection only, no SF queries
python snowflake_setup/run_spider2_lite_sf_agent.py --limit 1
python snowflake_setup/run_spider2_lite_sf_agent.py --limit 3
python snowflake_setup/run_spider2_lite_sf_agent.py --limit 10
```

All three runs already executed in this session; each produced a
`outputs/snowflake/runs/sf_limit{1,3,10}_*/` directory with
`predictions.jsonl` containing `mode=blocked_missing_snowflake_database`
and full readiness snapshot. No Snowflake queries issued — the gate
correctly refused even with `--execute true`.

### After the share lands

```bash
# Verify shares attached
python snowflake_setup/probe_databases.py
# (expect MISSING list to shrink to 0)

# Then ramp up — readiness gate will let you through:
python snowflake_setup/run_spider2_lite_sf_agent.py --limit 1 --execute true
python snowflake_setup/run_spider2_lite_sf_agent.py --limit 3 --execute true
python snowflake_setup/run_spider2_lite_sf_agent.py --limit 10 --execute true
# Full only after explicit confirmation; --max-bytes-confirm flag reserved.
```

## Spider2-Lite SQLite (B_sqlite lane)

Already executed in Phase 9 (commit `0f70a5c`). 135 items, exec_ok
35.6%, parse 96.3%, labeled "non-comparable to official EX" because
the bundled `.duckdb` is sample data, not the full warehouse.

## Spider2-Snow

Deferred until Spider2-Lite SF lane is unblocked. The same SF executor
+ schema index + prompting + agent will be reused with a different
task list (`spider2-snow.jsonl`). No new code until SF dbs are
attached.

## Spider2-DBT

- **Bridge:** committed in `af8d411`. Local generates, server
  evaluates. SSH `denis@103.54.18.91:/home/denis/dbt`. 68 task records
  validated.
- **Official evaluator:** wired in this PR. `spider2_dbt_bridge/server_side/server_official_eval.py`
  builds a per-task `result_dir/` with `results_metadata.jsonl` and
  the produced `.duckdb`, invokes upstream `evaluate.py`, captures
  rc + score + stdout/stderr.
- **Verified on asana001:** smoke run produced `eval_status: ok,
  official_score: {rate: 0.0, matched: 0, total: 1}, official_eval_rc:
  0`. The smoke SQL (`SELECT 1`) didn't match gold — expected.
- **End-to-end command:**
  ```bash
  TASK_ID=asana001
  python spider2_dbt_bridge/export_task_context.py --task-id $TASK_ID
  python spider2_dbt_bridge/build_model_prompt.py  --task-id $TASK_ID
  # drop model_response.txt for $TASK_ID
  python spider2_dbt_bridge/apply_model_output.py     --task-id $TASK_ID
  python spider2_dbt_bridge/run_remote_evaluation.py  --task-id $TASK_ID
  ssh denis@103.54.18.91 "/home/denis/dbt/.venv/bin/python /home/denis/dbt/colab_bridge/server_official_eval.py --task-id $TASK_ID --write-result"
  python spider2_dbt_bridge/collect_remote_result.py  --task-id $TASK_ID
  cat data/spider2_dbt/tasks/$TASK_ID/result/result.json
  ```

## Safety guarantees applied across all tracks

- No API keys / private keys / passwords in any committed file.
- `.env` files gitignored under `snowflake_setup/.gitignore`.
- All SF queries: `query_tag` set, `STATEMENT_TIMEOUT_IN_SECONDS` set,
  `ROWS_PER_RESULTSET` capped, role/warehouse/database explicit.
- BQ queries: `maximum_bytes_billed=10**9` (1 GB) per query.
- DBT bridge: per-task workspace under `outputs/colab_bridge/tasks/<TASK>/workspace/`,
  upstream `vendor/Spider2/spider2-dbt/examples/` never modified.
- All runners refuse `--all` / full benchmark; `--limit` mandatory.

## Final blockers (concise)

1. **Spider2-Lite SF execution:** waits for Marketplace share or
   self-host to attach the 58 expected databases.
2. **Spider2-Snow execution:** same blocker as above.
3. **Spider2-DBT real model integration:** today the bridge accepts
   any `model_response.txt`; the natural next step is loading
   Coder-7B on Colab (the BQ v8 inference setup is reusable) and
   running on a few diverse DBT tasks to measure official scores.
4. **Spider2-Lite BQ (A_bq) reasoning gap:** 88/205 items
   exec_ok_but_rows_mismatch — fixing this is independent of the SF
   work and would lift overall Spider2-Lite BQ EX above 10%.
