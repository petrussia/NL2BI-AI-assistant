# Spider2-DBT no-leakage policy

_Submission-style runs MUST NOT see gold information. Diagnostic /
oracle / error-analysis runs MAY see gold but MUST be labeled. This
doc enumerates exactly what counts as gold, where it lives, what the
allowed and forbidden uses are, and how to check at PR-review time._

## What counts as "gold" for Spider2-DBT

The official Spider2-DBT release at
`/home/denis/dbt/vendor/Spider2/spider2-dbt/evaluation_suite/gold/`
contains:

| Path | Forbidden in submission flow? | Notes |
|---|---|---|
| `gold/spider2_eval.jsonl` | YES | per-task evaluator spec: `{instance_id, evaluation: {func, parameters: {gold, condition_tabs, condition_cols, ignore_orders}}}` |
| `gold/<instance_id>/<gold_db>.duckdb` | YES | the gold-table .duckdb — never read by submission code |
| `gold/<instance_id>/...` | YES | any per-task gold artifact (csv, txt) |

Plus auxiliary files that are NOT gold but easy to confuse:

| Path | Forbidden? | Notes |
|---|---|---|
| `examples/<instance_id>/*` | NO | upstream example dir is the agent's raw input |
| `examples/<instance_id>/<db>.duckdb` | NO | the *upstream sample* DuckDB (often empty / partial) |
| `evaluation_suite/evaluate.py` | NO | the binary itself; the agent never reads its source |
| `evaluation_suite/eval_utils.py` | NO | helpers used by `evaluate.py` |

## Three flow modes

### Mode A — Submission flow

What runs: planner → context builder → candidate generator → executor → repair → selector → official_eval.

What it can see:
- `examples/<instance_id>/` (the upstream project the agent is supposed to fix)
- `spider2-dbt.jsonl` (instruction text only)
- prior-run logs from THIS task in THIS variant (Phase 5 repair feedback)
- per-task taxonomy label (allowed; computed offline once)
- planner output for this task (allowed; planner output is INPUT, not GOLD)

What it CANNOT see:
- `gold/spider2_eval.jsonl`
- `gold/<instance_id>/<gold_db>.duckdb` rows or schemas
- any column-name list extracted from the gold .duckdb
- gold's `condition_tabs` or `condition_cols` content
- another task's gold artifact even if it shares names

How it's enforced:
- The bridge code path that builds prompts (`build_model_prompt*.py`,
  the planner LLM call, the retrieval graph builder) NEVER opens any
  file under `evaluation_suite/gold/`.
- The bridge's apply step writes to a per-task workspace
  `outputs/colab_bridge/tasks/<task>__<variant>/workspace/`
  that is `cp -R`'d from `examples/<task>/`, NOT from `gold/<task>/`.
- The official evaluator runs as a separate process, AFTER everything
  else; its output (`evaluator_score_matched`) is captured but never
  fed back into the prompt.

### Mode B — Oracle diagnostic

What runs: gold-aware analysis scripts that help us understand WHERE the agent failed but never produce a submission-style prediction.

What it can see:
- everything in `gold/`
- everything in `examples/`
- per-(task, variant) `result.json` and `model_response.txt` from a prior submission run

What it produces:
- offline reports under `outputs/dbt_oracle_diagnostic/<run_id>/`
- per-task error-bucket distribution
- "what would the agent need to know" deltas
- an upper-bound estimate ("if the agent had been told the target file is X, would V4 have succeeded?")

What it must NOT do:
- write back into `data/spider2_dbt/tasks/<iid>/` paths used by Mode A
- influence `model_response_<variant>.txt` for any variant that will be reported
- be invoked by the live runner

How it's labeled: every output file produced by Mode B starts with the line
```
# ORACLE_DIAGNOSTIC_OUTPUT — DO NOT FEED INTO SUBMISSION FLOW
```
and lives under `outputs/dbt_oracle_diagnostic/`.

### Mode C — Error analysis

What runs: post-hoc analysis of submission run results. Does not need gold beyond what the official evaluator already exposed via `result.json` (which is just `matched=0/1`).

What it can see:
- the same things Mode A produced
- aggregated taxonomy from Phase 0
- `result.json`'s public fields

What it CANNOT see:
- gold rows, columns, or specs

This is the safest mode and is used for the diploma's tables / plots.

## Concrete forbidden patterns

### Forbidden 1: extracting gold table column names into the prompt

```python
# DO NOT DO THIS in any submission-flow code:
import duckdb
gold_db = f'/home/denis/dbt/vendor/Spider2/spider2-dbt/evaluation_suite/gold/{iid}/asana.duckdb'
con = duckdb.connect(gold_db, read_only=True)
gold_cols = con.execute("SELECT column_name FROM information_schema.columns WHERE table_name='asana__user'").fetchall()
prompt += f'Output must have these columns: {gold_cols}'  # GOLD LEAK
```

### Forbidden 2: copying gold's condition_tabs into the planner

```python
# DO NOT DO THIS:
gold_spec = json.load(open('.../gold/spider2_eval.jsonl'))
target = gold_spec[iid]['evaluation']['parameters']['condition_tabs'][0]
planner_input += f'Target table is {target}'  # GOLD LEAK
```

### Forbidden 3: training / few-shot examples drawn from gold

Gold is for grading, not demonstration. Few-shot examples must come from a
DIFFERENT corpus (e.g. dbt-hub package READMEs, dbt-core docs).

### Allowed: using upstream example's `examples/<iid>/` files freely

The upstream example dir IS the agent's working environment. Reading any
file under it is allowed and expected. This includes reading the
`<db>.duckdb` file in the example dir (it's *sample* data, not gold).

### Allowed: planner output

The planner LLM call is allowed to inspect the example dir and produce
target_file / action_type. This is part of the agent. Planner output
becomes a prompt input for the generator; nothing here is "gold".

## Pre-PR checklist (manual)

When opening a PR that adds or changes Mode-A code:

1. `git diff <branch>...HEAD -- spider2_dbt_bridge/ tools/remote_scripts/` and read every line. Look for:
   - any `evaluation_suite/gold` substring
   - any `condition_tabs` substring
   - any `gold_target` / `gold_table` substring
2. `grep -nR 'gold' spider2_dbt_bridge/ tools/remote_scripts/_*dbt*.py`. Every match must be either (a) in a comment explaining what's forbidden, or (b) in Mode-B / Mode-C code with the right header.
3. For any new prompt template, search the prompt body for occurrences of column names that appear ONLY in gold tables.
4. Run a smoke task and inspect the resulting `prompt.txt`: it must not contain anything mined from `evaluation_suite/gold/`.

## Pre-commit checklist (automated)

Add to `tools/check_no_leakage.py` (Phase 0 deliverable):

```python
import os, re, sys
from pathlib import Path

BAD = ('evaluation_suite/gold', 'condition_tabs', 'condition_cols',
        'gold_target', 'gold_db_path', 'load_gold_csv')
ALLOWED_DIRS = ('outputs/dbt_oracle_diagnostic',
                  'outputs/logs/spider2_dbt_no_leakage_policy.md')

def main():
    rc = 0
    repo = Path(__file__).resolve().parents[1]
    for p in repo.rglob('*.py'):
        if any(str(p).startswith(str(repo / a)) for a in ALLOWED_DIRS):
            continue
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for bad in BAD:
            for m in re.finditer(bad, text):
                # tolerate comments
                line_start = text.rfind('\n', 0, m.start()) + 1
                line = text[line_start: text.find('\n', m.start())]
                if line.lstrip().startswith('#'): continue
                if 'no_leakage_policy' in line.lower(): continue
                print(f'LEAK: {p}:{text.count(chr(10), 0, m.start())+1} '
                      f'matched {bad!r}')
                rc = 1
    sys.exit(rc)
```

This script runs in CI / pre-commit. Refuses to land any commit where
non-comment, non-Mode-B code references gold.

## Auditing prior commits

The current bridge code (commits up to `8f57eea`) was hand-checked against
the policy. Concrete review:

- `spider2_dbt_bridge/build_model_prompt.py` and
  `spider2_dbt_bridge/build_model_prompt_v2.py` — read only `task_files/`
  and `duckdb_tables.json` (both derived from upstream `examples/<iid>/`,
  not gold). PASS.
- `spider2_dbt_bridge/server_side/server_official_eval.py` — invokes
  `evaluate.py` AFTER apply + dbt run. Reads gold path but never feeds
  into prompt. PASS.
- `spider2_dbt_bridge/run_dbt_ablation.py` — reads `examples/spider2-dbt.jsonl`
  only for instruction; calls `server_official_eval.py` only after the
  agent has produced its output. PASS.

If a future PR fails the script above, it gets reverted before merge.

## What goes in the diploma

In the diploma's evaluation chapter:

- Submission flow runs: ALL Mode-A. These are the only numbers that count
  toward "Spider2-DBT score under our agent."
- Oracle diagnostic results: shown as **upper bounds**, clearly labeled,
  not as the agent's score.
- Error analysis: per-bucket stats, no gold leak.

The story is: "We built an agent that produces the score X under
no-leakage discipline. Oracle diagnostics show the upper bound is Y —
the gap between X and Y is the future-work gap."
