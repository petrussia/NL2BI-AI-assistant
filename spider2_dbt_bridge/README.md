# Spider2-DBT bridge — local generates, server evaluates

The model runs **locally / in Colab**, the dbt project runs on the server
(`denis@103.54.18.91:/home/denis/dbt`). The server holds 68 Spider2-DBT
tasks under `vendor/Spider2/spider2-dbt/examples/<instance_id>/` and never
needs `OPENAI_API_KEY` / `AZURE_API_KEY` / HF model weights.

The flow is **single-task, manual mode** by default. No full benchmark runs.

## Files

| Path | Role |
|---|---|
| `config.example.yaml` | SSH + remote/local paths (copy to `config.yaml`) |
| `ssh_utils.py` | tiny SSH/SCP helper, no extra deps |
| `inspect_remote_spider2_dbt.py` | dump task list to `reports/spider2_dbt_tasks_index.json` |
| `export_task_context.py` | pull a task's instruction + project files + duckdb schema → `data/spider2_dbt/tasks/<TASK>/context/` |
| `build_model_prompt.py` | assemble `prompt.txt` for the local/Colab model |
| `apply_model_output.py` | parse `model_response.txt` (SQL block or unified diff) and ship to a per-task workspace on the server |
| `run_remote_evaluation.py` | `dbt deps && dbt run && dbt test` inside the workspace; capture logs + result.json on the server |
| `collect_remote_result.py` | scp result.json + logs + dbt artifacts back into `data/spider2_dbt/tasks/<TASK>/result/` |
| `run_one_task_pipeline.py` | orchestrator: glue all five steps in `manual` mode |

## One-time setup

```bash
# Local
cp spider2_dbt_bridge/config.example.yaml spider2_dbt_bridge/config.yaml
# (edit if your SSH user/host differ from defaults)

# Confirm SSH passwordless
ssh -o BatchMode=yes denis@103.54.18.91 "echo SSH_OK"
```

No `pip install` needed. The bridge uses stdlib + your local OpenSSH.

## Quickstart for one task

```bash
# 1. inspect — produces reports/spider2_dbt_tasks_index.json (68 entries)
python spider2_dbt_bridge/inspect_remote_spider2_dbt.py

# 2. pick a task and pull its context locally
python spider2_dbt_bridge/export_task_context.py --task-id asana001

# 3. build the prompt
python spider2_dbt_bridge/build_model_prompt.py --task-id asana001
#    -> data/spider2_dbt/tasks/asana001/prompt.txt

# 4. (manual) feed prompt.txt to your model in Colab and save the
#    model's reply to data/spider2_dbt/tasks/asana001/model_response.txt
#    (the orchestrator below polls for this file)

# 5. apply + eval + collect via the orchestrator
python spider2_dbt_bridge/run_one_task_pipeline.py --task-id asana001 --mode manual
```

Or step-by-step:

```bash
python spider2_dbt_bridge/apply_model_output.py    --task-id asana001
python spider2_dbt_bridge/run_remote_evaluation.py --task-id asana001
python spider2_dbt_bridge/collect_remote_result.py --task-id asana001
```

## Exchange contract

Local: `data/spider2_dbt/tasks/<TASK_ID>/`

| File | Producer | Notes |
|---|---|---|
| `context/context.json` | export | task instruction + paths + step_idx |
| `context/duckdb_tables.json` | export | DuckDB tables + columns from the task's `.duckdb` files |
| `context/task_files/` | export | snapshot of `dbt_project.yml`, `profiles.yml`, `models/`, etc. |
| `prompt.txt` | build_prompt | model-ready prompt (single-shot) |
| `model_response.txt` | YOU / Colab | raw model output: SQL fenced block with `path=...` OR unified diff |
| `apply_manifest.json` | apply | which files were materialized + pushed |
| `result/result.json` | collect | dbt rc, eval status, overall_ok |
| `result/logs/dbt_run.log` | collect | full dbt run output |
| `result/target/run_results.json` | collect | dbt's own per-model run summary |
| `result/workspace_snapshot.tgz` | collect | full final workspace (excluding bulk) |

Server: `/home/denis/dbt/outputs/colab_bridge/tasks/<TASK_ID>/`

```
context/             # mirrored from local for audit (small files only)
workspace/           # rsync'd copy of vendor/Spider2/...examples/<iid>/
incoming/            # raw model_response.txt as received
patches/             # patch.diff history if diff form was used
logs/                # dbt_deps.log, dbt_run.log, dbt_test.log
result.json          # summary written by run_remote_evaluation.py
```

## Inference backend

Pluggable via `--mode`:

| mode | meaning |
|---|---|
| `manual` (default) | Pipeline polls `data/spider2_dbt/tasks/<TASK>/model_response.txt`. Human / Colab drops it. |
| `colab_file` | Alias for `manual`. |
| `local_function` | Reserved — pass a Python callable to the orchestrator. Not wired in this PR; keep `manual` for now. |
| `hf_local` | Reserved for `transformers` inference on the local box. Not wired. |

The model itself never lands on the server.

## Safety

- Only `--task-id` is accepted; no `--all`. The bridge refuses full benchmark.
- Server-side workspace is always copy-on-write under
  `outputs/colab_bridge/tasks/<TASK_ID>/workspace/`. The upstream
  `vendor/Spider2/spider2-dbt/examples/<iid>/` is read-only from the
  bridge's perspective.
- No API keys are ever sent to the server. The dbt + duckdb stack the
  server uses needs none of them.
- `config.yaml` is gitignored at repo root (or add `spider2_dbt_bridge/config.yaml`
  to `.gitignore` if you customize it).
- No SSH key material is touched by the bridge — it relies on the
  user's existing OpenSSH agent / `~/.ssh/config`.

## Where the LLM lives in upstream Spider2-DBT (so we know what we bypass)

Read on the server:

```
/home/denis/dbt/vendor/Spider2/methods/spider-agent-dbt/
    run.py
    spider_agent/agent/agents.py     # PromptAgent.run() = ReAct loop
    spider_agent/agent/models.py     # call_llm(payload) — OpenAI / Azure / Gemini / Groq / dashscope
```

The bridge **does not invoke `run.py`**. We replicate just the
"export instruction + project files → run dbt → collect" steps locally,
plus a one-shot prompt to the local model that emits a SQL/diff in a
fenced block. Multi-step ReAct is intentionally deferred.

## What's NOT here yet

- **Multi-step ReAct loop**: today is single-shot. Multi-step requires
  a stateful loop with growing observations (server emits new context
  after each apply+dbt; Colab loops until `Terminate`).
- **Spider2 evaluator integration**: `evaluation_suite/evaluate.py`
  compares predicted vs gold output. Right now we run dbt and capture
  status; `result.json["eval_status"] = "not_implemented"` until the
  evaluator wrapper is added.
- **`dbt deps` cache**: each task currently re-runs `dbt deps`. Cache
  reuse across tasks is a future optimization (some tasks share
  `dbt-utils` etc.).

See `risks.md` for the full risk register.
