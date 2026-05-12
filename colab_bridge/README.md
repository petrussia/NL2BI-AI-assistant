# Spider2-DBT Colab/server bridge

_Architecture for running Spider2-DBT tasks where the **server**
(`denis@petrthefirst24.fvds.ru:/home/denis/dbt`) holds the dbt environment
and runs commands, but the **LLM inference happens in Colab** (Coder-7B
on L4). Models stay in Colab; the server never downloads HF weights._

This folder is the local mirror of what should land at
`/home/denis/dbt/colab_bridge/` on the server. Copy with:

```
scp -r colab_bridge denis@petrthefirst24.fvds.ru:/home/denis/dbt/
```

Nothing here triggers the full 68-task benchmark. The flow is
single-shot per task: pick `--task-id <ID>`, export → infer in Colab
→ apply → dbt → collect → repeat manually.

## Where the LLM lives in Spider2-DBT (so we know what to bypass)

Read directly from the upstream Spider2 repo
(`xlang-ai/Spider2/methods/spider-agent-dbt/`):

- **`run.py`** is just a runner; it constructs `PromptAgent(...)` and
  calls `agent.run()` per task.
- **`spider_agent/agent/agents.py::PromptAgent.run()`** is the ReAct
  loop:
  ```python
  def run(self):
      done = False; step_idx = 0
      obs = "You are in the folder now."
      while not done and step_idx < self.max_steps:
          _, action = self.predict(obs)        # <- LLM call
          obs, done = self.env.step(action)    # <- dbt / bash / SQL
          step_idx += 1
  ```
- **`spider_agent/agent/agents.py::PromptAgent.predict()`** delegates to
  `call_llm()` from `spider_agent/agent/models.py`. The LLM is
  configured via `--model gpt-4o` (default OpenAI) but the upstream
  client also supports Azure / Gemini / Anthropic.
- **System prompt** is `BIGQUERY_SYSTEM` / `SNOWFLAKE_SYSTEM` /
  `LOCAL_SYSTEM.format(work_dir, action_space, task, max_steps)` —
  i.e. the dbt-local lane reads `LOCAL_SYSTEM`. We will reuse it.
- **Action vocabulary** for the local-DBT lane:
  `[Bash, Terminate, CreateFile, EditFile, LOCAL_DB_SQL]`. No
  BigQuery / Snowflake actions here — only DuckDB-via-dbt.
- The agent loop tolerates up to 3 parse failures, then aborts.

**To bypass server-side OpenAI**: we replace the `predict()` LLM call
with a file-exchange round trip:
- server writes `context.json` (instruction + obs + step_idx)
- Colab reads, runs Coder-7B, writes `model_response.txt` (one action)
- server parses, runs `env.step(action)`, appends new obs, loops.

The first iteration here implements **only the single-shot variant**
(one round of LLM, then dbt, then collect). The full iterative ReAct
bridge is a follow-up — flagged at the bottom of this README.

## Files

| Path | Role |
|---|---|
| `server_task_export.py` | Pick a task by `--task-id`, dump instruction + initial files into `outputs/colab_bridge/tasks/<task>/context.json`. Server-side. |
| `server_apply_patch.py` | Apply `model_response.txt` (raw SQL or unified diff) to the task's working directory. Server-side. |
| `server_run_dbt_for_task.py` | `dbt run` + `dbt test` in the task's project dir, capture stdout to `dbt_run.log`. Server-side. |
| `server_collect_task_result.py` | Collect run_results.json + manifest.json + status; write `result.json`. Server-side. |
| `colab_client_template.py` | Colab notebook helper: scp context.json down, format prompt, call local LLM, scp model_response.txt back. Colab-side. |
| `ssh_config_example.txt` | SSH alias template for the server. Colab-side. |
| `risks.md` | Known limitations + scope. |

## Server install (one-time)

```bash
ssh denis@petrthefirst24.fvds.ru
cd /home/denis/dbt
mkdir -p outputs/colab_bridge/tasks
# (after scp from your laptop:)
chmod +x colab_bridge/server_*.py 2>/dev/null || true
# ensure deps already there: dbt-duckdb, jq
which dbt && dbt --version
```

The server scripts use only stdlib + dbt CLI (no extra Python packages).

## End-to-end commands (single task)

```bash
# 1. on the server: pick a task and export its context for Colab
ssh denis@petrthefirst24.fvds.ru
cd /home/denis/dbt
python colab_bridge/server_task_export.py --task-id <TASK_ID>
# → outputs/colab_bridge/tasks/<TASK_ID>/context.json

# 2. in Colab: pull context, run model, push response
python colab_bridge/colab_client_template.py \
    --ssh-host denis@petrthefirst24.fvds.ru \
    --task-id <TASK_ID> \
    --model qwen-coder-7b
# → outputs/colab_bridge/tasks/<TASK_ID>/model_response.txt (server side)

# 3. on the server: apply, run dbt, collect
python colab_bridge/server_apply_patch.py    --task-id <TASK_ID>
python colab_bridge/server_run_dbt_for_task.py --task-id <TASK_ID>
python colab_bridge/server_collect_task_result.py --task-id <TASK_ID>
# → outputs/colab_bridge/tasks/<TASK_ID>/result.json
```

Or with a one-shot wrapper on the server:
```bash
TASK_ID=local005
python colab_bridge/server_task_export.py     --task-id "$TASK_ID"
# (wait for Colab response to land in tasks/$TASK_ID/model_response.txt)
python colab_bridge/server_apply_patch.py     --task-id "$TASK_ID"
python colab_bridge/server_run_dbt_for_task.py --task-id "$TASK_ID"
python colab_bridge/server_collect_task_result.py --task-id "$TASK_ID"
cat outputs/colab_bridge/tasks/"$TASK_ID"/result.json
```

## Exchange contract

Per-task directory `outputs/colab_bridge/tasks/<TASK_ID>/`:

| File | Producer | Format |
|---|---|---|
| `context.json` | server (export) | JSON with `task_id`, `instruction`, `db_engine`, `dbt_project_dir`, `files` (list of {path, sha256, size}), `pre_exec_dbt_status`, `step_idx` (0 for single-shot) |
| `task_files/*` | server (export) | snapshot of relevant files from the dbt project, ready for prompt construction |
| `model_response.txt` | Colab | raw model output. Parsed by `server_apply_patch.py` to extract one action: SQL block (most common for DBT lane), unified diff, or `Terminate("answer here")` |
| `patch.diff` | server (after apply) | optional canonical diff form for audit |
| `dbt_run.log` | server (dbt) | combined stdout+stderr of `dbt run` and `dbt test` |
| `result.json` | server (collect) | JSON with `task_id`, `dbt_status`, `n_models_passed`, `n_tests_passed`, `error_summary`, `eval_status` (when an evaluator is wired), `applied_action_kind`, `step_idx` |

## Security/scope guarantees

- **No HF model weights downloaded to the server.** Server scripts
  never call `transformers` / `huggingface_hub`. Only stdlib + dbt CLI.
- **No secrets in this folder.** SSH credentials live in the Colab
  user's `~/.ssh/`. The bridge does not handle keys directly.
- **No full-benchmark loop.** All scripts take `--task-id` and refuse
  to run if it's missing. There is no `--all` flag by design.
- **One-task-at-a-time.** Server scripts emit a clear "BUSY" sentinel
  if a task is mid-flight (presence of `task_files/` without `result.json`).

## What's intentionally NOT here yet

- **Iterative ReAct loop.** Today it's single-shot: one LLM round, one
  dbt run. Multi-step support requires a stateful loop on the server
  (re-emit context.json with growing observations) and Colab side
  (loop until `Terminate` or `max_steps`). Scaffolded in
  `risks.md` but not implemented.
- **Other action types beyond LOCAL_DB_SQL / SQL block / unified diff.**
  Bash/CreateFile/EditFile/Terminate parsing exists in
  `server_apply_patch.py` but the parsers are deliberately strict —
  the model must emit one of the documented forms exactly.
- **Spider2-DBT evaluator integration.** Right now we run dbt and
  capture status; comparing against gold (`exec_result.csv` /
  manifest expectations) is a follow-up. `result.json` carries
  `eval_status: "not_implemented"` until that lands.
