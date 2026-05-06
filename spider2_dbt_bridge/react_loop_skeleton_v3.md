# V3 multi-step ReAct — design skeleton (deferred from full run)

_Not implemented in this PR. Designs the state machine and exchange
contract that would extend the bridge from single-shot to multi-step._

## Why ReAct for Spider2-DBT

Spider2-DBT tasks frequently require **2–4 cooperating model files**:
a staging model → a transform model → a final model that the gold
spec scores. The current bridge issues one prompt → one model_response
→ one apply → one dbt run. If the model emits only one file but the
gold expects three, we lose by construction.

The official Spider2 agent runs a ReAct loop with up to `max_steps=30`
actions. The loop alternates: predict next action / observe its
result / decide next action. The right action set for our DBT lane
includes: write/edit a model file, run dbt for a subset of models,
read a file, list directory, terminate.

## Proposed v3 contract (single-task, server-stateful)

```
[step 0]
  server: emit context.json with
    instruction, project_files_listing, duckdb_tables,
    step_idx=0,
    history=[]
  Colab: read, ask Coder-7B for one action JSON,
    write model_response.txt with:
      {"action": "write_file",
       "args": {"path": "models/asana__user.sql", "body": "WITH ... SELECT ..."},
       "reason_short": "build the user-level fact required by gold"}
[step 1]
  server: parse action, apply, execute the side-effect (write file
    or run dbt or list dir), capture observation, append to history,
    increment step_idx, emit new context.json
  Colab: read updated context.json (now has history), ask for next
    action; eventually emits {"action":"terminate","args":{}}
[step N]
  server: official_eval the final workspace, write result.json
```

## Action vocabulary (subset)

| Action | Args | Effect |
|---|---|---|
| `write_file` | `path, body` | Create/overwrite model SQL file |
| `edit_file` | `path, find, replace` | Targeted small edit |
| `list_models` | (none) | Enumerate workspace `models/` |
| `read_file` | `path` | Return file contents to next obs |
| `dbt_run` | `select?` | Run `dbt run` (optionally `--select X`) |
| `dbt_test` | `select?` | Run `dbt test` |
| `terminate` | (none) | Stop, run official eval |

Hard cap `max_steps = 8` (DBT tasks are tractable in <8 steps; the
official agent uses 30 but we don't need that for the simpler subset).
Repeat-detection: if model emits the same action JSON twice in a row,
force-terminate.

## What this PR did NOT implement

- The server scaffolding to emit/refresh `context.json` with growing
  history. Today `export_task_context.py` writes once, no step counter.
- The Colab-side `model_response.txt` polling loop on the server.
- A proper observation formatter (truncating dbt output, summarizing
  file lists).

## What this PR DID test (V1/V2/V4)

The grounding-improvement story (V2) and the diff-priority story (V4)
do not require ReAct — they are pure prompt engineering. Both are
implemented and benchmarked in `outputs/dbt_ablation/ablation_main/`.

## Estimated cost of implementing V3

- ~150 lines of server-side state machine
- ~80 lines of Colab-side loop driver
- 6 tasks × 8 steps × ~10 sec inference per step ≈ 8 minutes per
  variant for the same 6-task sample
- The cleanest place to put it would be alongside
  `run_dbt_ablation.py` as `run_dbt_react.py`, sharing the apply +
  dbt_run subroutines.

## Recommended next step

Implement V3 only if V2/V4 ablation shows the prompt-only improvements
are insufficient (i.e. very few items reach `dbt_run_rc=0` even with
better grounding). If V2/V4 already gets non-trivial compile pass,
the higher-leverage next step is **fixing the upstream Spider2-DBT
test failures** that account for most of the 21 ERROR per task in our
runs (these are not our model's fault — they're pre-existing source
config bugs).
