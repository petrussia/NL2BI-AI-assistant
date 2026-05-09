# Server-side colab_bridge (lives at /home/denis/dbt/colab_bridge/)

These scripts are invoked by the local-side bridge over SSH. They only
implement read/dispatch helpers — no Python deps beyond stdlib + the
project venv (`/home/denis/dbt/.venv`).

| Script | Purpose |
|---|---|
| `server_list_tasks.py` | Read `vendor/Spider2/spider2-dbt/examples/spider2-dbt.jsonl` and emit a JSON list with `instance_id`, `instruction`, `type`, `has_example_dir`. |
| `server_prepare_task_workspace.py` | rsync the upstream example dir into `outputs/colab_bridge/tasks/<TASK_ID>/workspace/`. Idempotent — refuses to overwrite a workspace that already has `.duckdb_wal` (i.e. dbt was already running). |
| `server_run_task_eval.py` | Activate venv + `cd workspace` + `dbt deps && dbt run && dbt test`. Logs go to `tasks/<TASK_ID>/logs/`. Writes `tasks/<TASK_ID>/result.json`. |
| `server_collect_result.py` | Tar a small bundle of `result.json + logs + target/*.json` for the local side to fetch (the local side already does this with scp; this is a convenience). |

The local-side bridge orchestrates everything. These server scripts are
small, idempotent, and can be invoked by hand for debugging.

## Manual usage on the server

```bash
cd /home/denis/dbt
# list tasks
python colab_bridge/server_list_tasks.py | head

# prepare a workspace
python colab_bridge/server_prepare_task_workspace.py --task-id asana001

# (the local bridge would normally drop edits here)
# /home/denis/dbt/outputs/colab_bridge/tasks/asana001/workspace/models/output.sql

# run dbt
python colab_bridge/server_run_task_eval.py --task-id asana001

# inspect result
cat /home/denis/dbt/outputs/colab_bridge/tasks/asana001/result.json
```
