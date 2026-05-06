# Spider2-DBT — first real-model end-to-end run

_Task: `asana001`. Model: Qwen2.5-Coder-7B-Instruct (BF16) on Colab L4
GPU. Bridge: HTTPS `discussions-wake-acute-dream.trycloudflare.com`.
Server: `denis@103.54.18.91`._

## What ran

```
local                       Colab GPU                       VPS server
────────────────            ────────────────                ────────────────
build_model_prompt   ──→   prompt.txt
                            │
                            ▼
                     Coder-7B inference   (8254 chars in,
                     (cached load ~7s,     1500 max_new tokens out,
                     gen ~30s)             actual 662 chars response)
                            │
                            ▼
model_response.txt  ◄──── (base64 over HTTPS)
       │
       ▼
apply_model_output  ──────────────────────────→  workspace/models/asana__metrics.sql
                                                 (cp -R from upstream + push file)
                                                          │
                                                          ▼
run_remote_evaluation  ──────────────────────→   dbt deps  → dbt run → dbt test
                                                 30 PASS / 21 ERROR
                                                          │
                                                          ▼
server_official_eval  ───────────────────────→   Spider2 evaluate.py
                                                 eval_status=ok
                                                 score=0/1 rc=0
                                                          │
                                                          ▼
collect_remote_result ◄──────────────────────── result.json + logs + .duckdb tar
```

## Numbers

| Metric | Value |
|---|---|
| Prompt size | 8254 chars |
| Tokens generated | up to 1500 (actual 662 chars decoded) |
| dbt_deps_rc | 0 |
| dbt_run_rc | 1 (compile error in our generated model — see below) |
| dbt_test_rc | 1 |
| dbt PASS / ERROR | 30 / 21 (the 21 are pre-existing upstream test failures) |
| `eval_status` | `ok` |
| `official_score.rate` | **0.0** |
| `official_score.matched` | 0 |
| `official_score.total` | 1 |
| `official_eval_rc` | 0 |

## What the model wrote

```sql
-- models/asana__metrics.sql
with task as (
    select * from {{ ref('asana__task') }}
),
completed_tasks as (
    select task_id, completed_at from task where is_completed = true
),
open_tasks as (
    select task_id, created_at from task where is_completed = false
),
avg_close_time as (
    select avg(completed_at - created_at) as avg_close_duration
    from completed_tasks
)
select
    (select count(*) from open_tasks) as open_tasks_count,
    (select count(*) from completed_tasks) as completed_tasks_count,
    (select avg_close_duration from avg_close_time) as avg_close_time
```

This is plausible CTE-style dbt SQL with proper `{{ ref('asana__task') }}`
upstream reference. The model understood the dbt/Jinja convention.

## Why the score is 0

The gold answer for `asana001` requires materializing **two specific
models**:

```
asana__team   (cols 0..9 must match)
asana__user   (cols 0..2 must match)
```

The model produced one different model (`asana__metrics`) summarizing
totals + averages. Even though the SQL itself is grammatically valid
dbt, it doesn't produce the expected *table contents* in the workspace
`.duckdb`. The official evaluator compares the workspace's
`asana.duckdb` against the gold `asana.duckdb` on the listed tables;
our run never created `asana__team` or `asana__user` with the right
shape, so `duckdb_match` returns 0.

The model also referenced `is_completed` / `completed_at` /
`created_at` columns that don't exist in the upstream `asana__task`
model (the actual columns are different). dbt errored out at compile
time on the new model — visible in `dbt_run.log` as
`Compilation Error... task does not have a column named
'is_completed'`. So the produced `.duckdb` doesn't have an
`asana__metrics` table either; it ran only the existing models.

## What this proves

- The bridge (model in Colab → SSH server → dbt → DuckDB → official
  evaluator → score back) runs **end-to-end with no manual steps after
  `build_model_prompt`**.
- The official Spider2-DBT evaluator can be invoked per-task by our
  server-side wrapper without disturbing upstream.
- Score is not a fluke 0 — it's the genuine evaluator output for a
  one-shot model attempt that misunderstood the task.

## Cost

- Colab GPU: ~1 minute of inference time.
- SSH/DBT execution: ~1 minute (rsync, deps, run, test).
- BigQuery / Snowflake: 0 (DBT lane uses local DuckDB).

## What would lift the score (next iteration)

1. **Better task understanding.** The prompt builder shows column
   schemas of `asana.duckdb` raw tables, but does NOT enumerate the
   columns of the *staging* models that the gold expects. Adding
   `models/staging/stg_asana__*.sql` model column lists into the
   prompt would steer the model toward the right materializations.
2. **Multi-shot.** Spider2-DBT often needs 3–4 model files to cooperate
   (a staging model, a transform model, a final model). Single-shot
   one-block output cannot satisfy that. The natural extension is the
   ReAct loop the bridge already accepts (server emits new context.json
   after each apply+run; Colab loops).
3. **Use existing structure.** The asana001 example already ships
   `models/asana__daily_metrics.sql`, `models/asana__project.sql`,
   `models/asana__tag.sql`, `models/asana__task.sql`. The gold names
   `asana__team` and `asana__user` are the missing pieces. A diff-style
   response that ADDS those two models specifically would have a
   higher chance of matching gold than a fresh `asana__metrics`.

## Reproduce

```bash
# Bridge URL must point at your live Colab tunnel:
#   https://discussions-wake-acute-dream.trycloudflare.com (or current)

TASK_ID=asana001

python spider2_dbt_bridge/export_task_context.py --task-id $TASK_ID
python spider2_dbt_bridge/build_model_prompt.py  --task-id $TASK_ID
python tools/remote_scripts/_run_dbt_inference.py $TASK_ID 1500
python spider2_dbt_bridge/apply_model_output.py     --task-id $TASK_ID
python spider2_dbt_bridge/run_remote_evaluation.py  --task-id $TASK_ID
ssh denis@103.54.18.91 "/home/denis/dbt/.venv/bin/python /home/denis/dbt/colab_bridge/server_official_eval.py --task-id $TASK_ID --write-result"
python spider2_dbt_bridge/collect_remote_result.py  --task-id $TASK_ID

cat data/spider2_dbt/tasks/$TASK_ID/result/result.json
```

Artifacts:
- [data/spider2_dbt/tasks/asana001/prompt.txt](../data/spider2_dbt/tasks/asana001/prompt.txt) (input)
- [data/spider2_dbt/tasks/asana001/model_response.txt](../data/spider2_dbt/tasks/asana001/model_response.txt) (Coder-7B output)
- [data/spider2_dbt/tasks/asana001/result/result.json](../data/spider2_dbt/tasks/asana001/result/result.json) (final summary with official_score)

## Verdict

The Spider2-DBT track is **operationally green** end-to-end.
Coder-7B's first one-shot answer doesn't satisfy gold for asana001
(genuine `0/1` score), but every link in the chain — model → bridge →
SSH → dbt → DuckDB → Spider2 evaluator → score — works without manual
intervention.
