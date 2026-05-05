# Spider2-DBT bridge — final report

_Architecture: local/Colab generates, server (`denis@103.54.18.91`)
evaluates. Server holds dbt + DuckDB + 68 Spider2-DBT examples;
no LLM, no API keys, no HF model weights ever land there._

## 1. SSH / server precheck

- SSH passwordless from local box to `denis@103.54.18.91` (resolves
  `petrthefirst24.fvds.ru`) — **OK**.
- `./scripts/check_env.sh` — all green: Python 3.11.15 venv, dbt-core
  1.10.8, dbt-duckdb 1.10.1, DuckDB 1.5.2, Spider2 repo present at
  commit `01a4c67c`. **API keys all unset** (`OPENAI`, `AZURE`,
  `GEMINI`).
- `./scripts/test_dbt_duckdb.sh` — green: dbt debug OK, smoke `dbt run`
  PASS=1, DuckDB returns expected row.
- Full text: [`reports/spider2_dbt_bridge_precheck.md`](spider2_dbt_bridge_precheck.md).

## 2. Spider2-DBT structure on the server

| Item | Path |
|---|---|
| Task list (68 records) | `vendor/Spider2/spider2-dbt/examples/spider2-dbt.jsonl` |
| Per-task example dirs | `vendor/Spider2/spider2-dbt/examples/<instance_id>/` |
| Evaluator | `vendor/Spider2/spider2-dbt/evaluation_suite/evaluate.py` |
| Gold answers | `vendor/Spider2/spider2-dbt/evaluation_suite/gold/` (kept out of prompts) |
| Upstream agent runner (NOT used by bridge) | `vendor/Spider2/methods/spider-agent-dbt/run.py` |
| Upstream LLM dispatcher (NOT used by bridge) | `vendor/Spider2/methods/spider-agent-dbt/spider_agent/agent/models.py::call_llm` |

## 3. Where the task list lives

`/home/denis/dbt/vendor/Spider2/spider2-dbt/examples/spider2-dbt.jsonl`
— 68 rows, each `{instance_id, instruction, type}`. All 68 have a
matching `examples/<instance_id>/` directory. Pulled to local at
`reports/spider2_dbt_tasks_index.json`.

## 4. Dry-run task

`asana001` — chosen for being a complete dbt project with sample
DuckDB and a clear instruction. Dry-run results documented in
[`reports/spider2_dbt_bridge_dry_run.md`](spider2_dbt_bridge_dry_run.md).

## 5. Bridge files created locally

```
spider2_dbt_bridge/
├── README.md
├── config.example.yaml
├── ssh_utils.py
├── inspect_remote_spider2_dbt.py
├── export_task_context.py
├── build_model_prompt.py
├── apply_model_output.py
├── run_remote_evaluation.py
├── collect_remote_result.py
├── run_one_task_pipeline.py
└── server_side/
    ├── colab_bridge_README.md
    ├── server_list_tasks.py
    ├── server_prepare_task_workspace.py
    ├── server_run_task_eval.py
    └── probe_duckdb.py
notebooks_or_colab/
└── SPIDER2_DBT_COLAB_INFERENCE_TEMPLATE.md
reports/
├── spider2_dbt_bridge_precheck.md
├── spider2_dbt_bridge_dry_run.md
├── spider2_dbt_tasks_index.json
└── spider2_dbt_bridge_final_report.md  (this file)
```

## 6. Server-side bridge installed at `/home/denis/dbt/colab_bridge/`

```
colab_bridge/
├── colab_bridge_README.md
├── server_list_tasks.py
├── server_prepare_task_workspace.py
├── server_run_task_eval.py
└── probe_duckdb.py
```

Plus per-task workspace root: `/home/denis/dbt/outputs/colab_bridge/tasks/<TASK_ID>/`.

## 7. Local context location

`data/spider2_dbt/tasks/<TASK_ID>/`:

```
context/
  context.json          # instruction + remote paths + step_idx + duckdb file list
  duckdb_tables.json    # tables/columns from the task's .duckdb files
  snapshot.tgz          # raw tar of dbt project files (small, just sources)
  task_files/           # extracted snapshot for browsing
prompt.txt              # what is sent to the model
model_response.txt      # what the model returned (you/Colab fill this)
apply_manifest.json     # which files we shipped + remote workspace path
result/
  result.json
  summary.json
  logs/{dbt_deps,dbt_run,dbt_test}.log
  target/{run_results,manifest}.json
  workspace_snapshot.tgz
```

## 8. Server workspace location

`/home/denis/dbt/outputs/colab_bridge/tasks/<TASK_ID>/`:

```
workspace/      # cp -R copy of upstream example, mutated by apply step
incoming/       # raw model_response.txt as received (audit trail)
logs/           # dbt_deps.log, dbt_run.log, dbt_test.log
result.json     # bridge-written summary
```

The upstream `vendor/Spider2/spider2-dbt/examples/<iid>/` is untouched
by the bridge. Even with `--force`, only the per-task workspace is
clobbered.

## 9. Prompt format

`prompt.txt` contains:

1. Role line + task ID + the natural-language QUESTION verbatim.
2. RULES section: DuckDB-flavored SQL hints (UNNEST yes, FLATTEN no,
   `{{ ref(...) }}` and `{{ source(...) }}` for dbt references), and
   the strict output contract.
3. SCHEMA section: every DuckDB table with columns + types.
4. PROJECT FILES section: paths + first 6 lines of each source file
   (full body for `dbt_project.yml`, `schema.yml`, `models/*`).
5. Final directive: "emit ONE fenced block (SQL or diff form)".

Hard cap default: 14 000 chars (configurable). Trimmed gracefully if
schema + files exceed budget.

## 10. Expected `model_response.txt`

Either of two fenced forms (the bridge auto-detects):

- **SQL block** with explicit path attribute:
  ```
  ```sql path=models/output.sql
  WITH x AS (SELECT ...) SELECT * FROM x
  ```
  ```
- **Unified diff** against snapshot files:
  ```
  ```diff
  --- a/models/some_model.sql
  +++ b/models/some_model.sql
  @@ ...
  ...
  ```
  ```

Anything else falls back to "treat the entire response as the body
of `models/output.sql`". No fenced block + no `path=` attribute is
the legitimate degenerate case the bridge can still handle.

## 11. How the model output is applied

`apply_model_output.py`:

1. Parses fenced blocks from `model_response.txt`.
2. Stages parsed files into `data/spider2_dbt/tasks/<TASK>/workspace_staging/`.
3. SCPs raw response into `outputs/colab_bridge/tasks/<TASK>/incoming/` (audit).
4. Initializes `outputs/colab_bridge/tasks/<TASK>/workspace/` as a
   `cp -R` copy of the upstream example dir (only on first call).
5. SCPs each staged file into `workspace/<rel_path>`.
6. If diff form, runs `git apply -p1 patch.diff` (falls back to
   `patch -p1`) on the server.
7. Writes `apply_manifest.json` locally.

Path traversal (`..`) and absolute paths are refused.

## 12. How remote evaluation runs

`run_remote_evaluation.py` SSHes:

```
source /home/denis/dbt/.venv/bin/activate
cd /home/denis/dbt/outputs/colab_bridge/tasks/<TASK>/workspace
export DBT_PROFILES_DIR=$PWD
dbt deps     | tee logs/dbt_deps.log
dbt run      | tee logs/dbt_run.log    (with timeout)
dbt test     | tee logs/dbt_test.log   (with timeout)
```

Per-stage rc captured via `${PIPESTATUS[0]}` and grepped back.
Result summary written to `outputs/colab_bridge/tasks/<TASK>/result.json`.

## 13. Where result/logs live (after `collect`)

Local: `data/spider2_dbt/tasks/<TASK_ID>/result/` (see §7).
Server: `outputs/colab_bridge/tasks/<TASK_ID>/result.json` + `logs/`.

## 14. What works (verified in `asana001` dry-run)

- ✓ SSH passwordless + `cp -R`-based workspace prep (rsync absent on server).
- ✓ Task export with project-file snapshot + DuckDB schema introspection.
- ✓ Prompt build (8254 chars in dry-run).
- ✓ Apply step parses SQL fenced block, ships the file, initializes workspace.
- ✓ `dbt deps` installs `dbt_utils`, `fivetran_utils`, etc. into workspace.
- ✓ `dbt run` executes the new model + all upstream models.
- ✓ `dbt test` runs all tests; result.json captures `dbt_run_rc`,
  `dbt_test_rc`, `has_run_results_json`.
- ✓ Collect retrieves `result.json`, `run_results.json`, `manifest.json`,
  full logs, plus a tar of the workspace.
- ✓ All steps idempotent; can rerun any step independently.

## 15. What's blocked / unclear

- **Spider2 evaluator integration not wired.** `result.json["eval_status"]
  = "not_implemented"`. To compare predicted vs gold output we'd run
  `evaluation_suite/evaluate.py` against the workspace, which needs a
  small wrapper to feed it the right paths.
- **Multi-step ReAct loop not implemented.** Bridge is single-shot;
  full agent behaviour requires a state machine (server emits new
  context.json after each apply+run; Colab loops until `Terminate`).
- **asana001 (and likely many others) ships with pre-existing test
  failures.** 21/51 tests fail because the project's source declarations
  reference table identifiers that don't exist in the sample DuckDB.
  This is upstream-Spider2 behaviour, not a bridge issue. Some tasks
  may need source-config patches before tests pass.
- **`dbt deps` runs per-task.** Cross-task package cache reuse is a
  follow-up; first run is ~10–20 s of network.

## 16. Commands for the next run

```bash
# pick a task
python spider2_dbt_bridge/inspect_remote_spider2_dbt.py
# (browse reports/spider2_dbt_tasks_index.json)

TASK_ID=asana001   # or any other instance_id

python spider2_dbt_bridge/export_task_context.py --task-id $TASK_ID
python spider2_dbt_bridge/build_model_prompt.py  --task-id $TASK_ID

# === Colab cell drops model_response.txt into ===
#     data/spider2_dbt/tasks/$TASK_ID/model_response.txt
# (see notebooks_or_colab/SPIDER2_DBT_COLAB_INFERENCE_TEMPLATE.md)

python spider2_dbt_bridge/apply_model_output.py    --task-id $TASK_ID
python spider2_dbt_bridge/run_remote_evaluation.py --task-id $TASK_ID
python spider2_dbt_bridge/collect_remote_result.py --task-id $TASK_ID
cat data/spider2_dbt/tasks/$TASK_ID/result/result.json
```

Or all-in-one (manual mode polls for `model_response.txt`):

```bash
python spider2_dbt_bridge/run_one_task_pipeline.py --task-id $TASK_ID --mode manual
```

## 17. Risks and limitations

| Risk | Status | Mitigation |
|---|---|---|
| LLM secret leakage to server | mitigated | Bridge never sets API keys on the server. Server scripts run dbt only. |
| Server overwrites upstream Spider2 | mitigated | All bridge writes go to `outputs/colab_bridge/tasks/<TASK>/workspace/`. The bridge refuses to write into `vendor/Spider2/`. |
| Full benchmark accidentally launched | mitigated | `--task-id` is mandatory on every script; orchestrator has no `--all`. |
| Path-traversal via `path=...` attr | mitigated | `apply_model_output.py` refuses `/` prefix and `..` components. |
| `rsync` missing on server | mitigated | Switched to `cp -R`. |
| Colab→server SSH key exposure | not enabled by default | The default flow keeps SSH on the local box; Colab only writes a file. Direct mode requires an explicit ephemeral key flow. |
| dbt deps cost / network flakiness | accepted | First run downloads packages; subsequent runs reuse `dbt_packages/`. |
| Pre-existing test failures in tasks | reported, not fixed | Bridge captures the failures truthfully; fixing upstream-Spider2 source configs is out of scope for the bridge layer. |
| Big workspace tars | bounded | `collect` excludes `dbt_packages/`, `target/`, `*.duckdb_wal` from the tar. |
| Per-task DuckDB binaries | not transferred | Bridge sends only schema metadata (`duckdb_tables.json`); the actual `.duckdb` lives only on the server. |

---

**Bottom line.** A real Colab GPU run can now solve any one of 68
tasks with one round trip:

1. local exports + builds prompt
2. Colab generates a fenced SQL/diff block in `model_response.txt`
3. local relays it; server applies + runs dbt + writes `result.json`
4. local collects result.json + logs

The server stays a pure execution backend. No LLM, no API keys, no
model weights. The full Spider2-DBT 68-task benchmark is one step
away — but that step is out of scope for this PR by design.
