# Spider2-DBT bridge — single-task dry run

_Task: `asana001`. Mode: `manual` (no live LLM). Goal: prove the
local-generates / server-evaluates pipeline works end-to-end._

## Sequence

```bash
# 1. Inventory tasks (writes reports/spider2_dbt_tasks_index.json)
python spider2_dbt_bridge/inspect_remote_spider2_dbt.py
# -> n_tasks=68 with_example_dir=68

# 2. Export task context
python spider2_dbt_bridge/export_task_context.py --task-id asana001
# -> data/spider2_dbt/tasks/asana001/context/{context.json, snapshot.tgz, task_files/, duckdb_tables.json}

# 3. Build prompt
python spider2_dbt_bridge/build_model_prompt.py --task-id asana001
# -> data/spider2_dbt/tasks/asana001/prompt.txt (8254 chars)

# 4. Drop a smoke "model_response.txt" to exercise apply path
#    (real run would have Colab fill this)
echo '```sql path=models/asana__bridge_smoke.sql
SELECT 1 AS bridge_smoke_marker
```' > data/spider2_dbt/tasks/asana001/model_response.txt

# 5. Apply to server workspace (cp -R copy of upstream example dir)
python spider2_dbt_bridge/apply_model_output.py --task-id asana001
# -> /home/denis/dbt/outputs/colab_bridge/tasks/asana001/workspace/models/asana__bridge_smoke.sql

# 6. Run dbt deps + dbt run + dbt test on the server
python spider2_dbt_bridge/run_remote_evaluation.py --task-id asana001
# -> rc=0 from SSH; dbt itself: deps OK, run OK, test 30 PASS / 21 ERROR
#    (the 21 errors are pre-existing test failures in the asana001 project,
#     not artifacts of the bridge or our smoke model)

# 7. Collect everything back
python spider2_dbt_bridge/collect_remote_result.py --task-id asana001
# -> data/spider2_dbt/tasks/asana001/result/{result.json, summary.json, logs/*, target/run_results.json, manifest.json, workspace_snapshot.tgz}
```

## Result

| Stage | Status | Evidence |
|---|---|---|
| SSH precheck | ✓ | reports/spider2_dbt_bridge_precheck.md |
| Inventory | ✓ | 68 tasks listed; all have example dirs |
| Export | ✓ | snapshot.tgz extracted; duckdb_tables.json with 1 db, 14 tables |
| Prompt build | ✓ | 8254 chars, schema + 22 source files inlined |
| Apply | ✓ | sql_file kind, 1 file pushed |
| Server prepare | ✓ | `cp -R` workspace from upstream example |
| dbt deps | ✓ | dbt-utils etc. installed in workspace/dbt_packages |
| dbt run | partial | model `asana__bridge_smoke` compiles OK; pre-existing models fail on substituted source identifiers — not a bridge issue |
| dbt test | partial | 30 tests PASS, 21 ERROR — same upstream issue |
| Collect | ✓ | result.json + run_results.json + manifest.json + logs + workspace tar all retrieved |
| Final result.json | overall_ok=False | because dbt_run_rc=1 (test failures) — but expected and correctly captured |

## What this dry-run proves

- **No server-side LLM call** required. The server scripts only run dbt /
  duckdb / cp / mkdir / shell utilities.
- **No HF model weights on the server.** Server scripts don't import
  `transformers` or touch `~/.cache/huggingface`.
- **No API keys present on server.** `OPENAI_API_KEY` etc. remained
  unset throughout (verified by `check_env.sh`).
- **Per-task isolation.** Workspace lives at
  `/home/denis/dbt/outputs/colab_bridge/tasks/asana001/workspace/`,
  not in `vendor/Spider2/spider2-dbt/examples/asana001/`.
- **Resumable.** All artifacts are file-based; we can rerun any step
  independently.
- **Audit trail.** Both raw `model_response.txt` and the parsed
  `apply_manifest.json` are stored locally and on the server
  (under `incoming/`).

## Known gaps to flag for the next iteration

1. **Spider2 evaluator integration.** `result.json["eval_status"]` is
   `not_implemented`. Wiring `evaluation_suite/evaluate.py` to compare
   the produced output table against gold is the next step.
2. **Multi-step ReAct.** Bridge is single-shot. Multi-step requires
   a state machine emitting new context.json after each apply+run.
3. **Pre-existing project test failures.** The asana001 example as
   shipped has 21 test errors (substituted source identifiers point
   at non-existent tables in the bundled sample DuckDB). This is
   upstream-Spider2 territory — bridge correctly records but doesn't
   try to fix.
4. **Cold-start cost.** First run does `dbt deps` (~10–20 s); future
   runs in the same workspace skip unless `--force`. Cross-task cache
   reuse not yet implemented.

## Conclusion

**Bridge is functional.** A real Colab-side model can now drop a
`model_response.txt` against `asana001` (or any of the 67 other tasks)
and get a `result/` bundle back without the server ever touching an
LLM.
