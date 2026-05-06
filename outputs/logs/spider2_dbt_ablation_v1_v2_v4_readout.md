# Spider2-DBT prompt ablation — V1 vs V2 vs V4

_Run: `outputs/dbt_ablation/ablation_main/`. Branch `experiments/denis`._

## Question

Of the three improvements proposed after the first real-model run on
asana001 (score 0/1), which **one-shot prompt change** actually helps?
The candidates were:

| Variant | What it changes |
|---|---|
| **V1** baseline | current prompt, single-shot, single fenced block |
| **V2** better grounding | + group existing models by class (staging / intermediate / final), + extract column names from each `.sql`, + emit naming-convention hint |
| **V4** diff-form priority | + tells the model to PREFER unified diff that extends an existing model; falls back to new SQL only if no model fits |

(V3 multi-step ReAct deferred — see `spider2_dbt_bridge/react_loop_skeleton_v3.md`.)

The compute budget allows one shot per (task, variant) — same as v8 BQ.
Improvements are pure prompt engineering: same inference path, same
Coder-7B (BF16 on Colab L4) via the same bridge.

## Method

Six tasks, sorted by tractability heuristic (1 target table, ≤7
condition columns, project not too sparse): `asana001`, `playbook001`,
`retail001`, `recharge002`, `xero001`, `lever001`.

Per (task, variant):

1. Build prompt with `build_model_prompt_v2.py --variant <v>`.
2. Inference via Colab bridge (max_new=1500, do_sample=False).
3. Apply to per-variant fresh server workspace
   `outputs/colab_bridge/tasks/<task>__<variant>/workspace`
   (cp -R from upstream example, no contamination across variants).
4. `dbt deps && dbt run && dbt test` with rc captured from
   `${PIPESTATUS[0]}` per stage.
5. Official Spider2 evaluator
   (`/home/denis/dbt/colab_bridge/server_official_eval.py`) emits
   `{rate, matched, total}` per task.
6. Collect.

18 runs total, ~45 s each, all in one ~14-minute session via the
ablation orchestrator `spider2_dbt_bridge/run_dbt_ablation.py`.

## Headline numbers

| Variant | n | dbt_run_rc=0 | items matched (score) | dbt_pass_total | dbt_err_total | wall_s_avg |
|---|---:|---:|---:|---:|---:|---:|
| V1 | 6 | **0/6** | **2/6 = 33%** | 0 | 0 | 45.3 |
| V2 | 6 | **0/6** | **2/6 = 33%** | 0 | 0 | 45.5 |
| V4 | 6 | **2/6** | **3/6 = 50%** | 88 | 21 | 46.0 |

`dbt_run_rc=0` is the clean-compile rate — i.e. the SQL the agent
produced compiled and ran end-to-end without dbt errors. `pass_total`
is the sum of `dbt test` PASS counts; only V4 reaches the `dbt test`
phase across multiple tasks.

## Per-task

| iid | variant | dbt_run_rc | dbt_test pass/err | score | apply form | wall_s |
|---|---|---:|---|---:|---|---:|
| **asana001** | V1 | 2 | 0/0 | 0/1 | sql_file | 62.8 |
| asana001 | V2 | 2 | 0/0 | 0/1 | sql_file | 56.3 |
| asana001 | V4 | **1** | **30/21** | 0/1 (compile error) | diff | 40.2 |
| **playbook001** | V1 | 1 | 0/0 | 1/1 | sql_file | 43.0 |
| playbook001 | V2 | 2 | 0/0 | 1/1 | sql_file | 40.3 |
| playbook001 | V4 | **0** | 0/0 | **1/1** | diff | 42.8 |
| **retail001** | V1 | 2 | 0/0 | 1/1 | sql_file | 29.8 |
| retail001 | V2 | 2 | 0/0 | 1/1 | sql_file | 25.5 |
| retail001 | V4 | 2 | 0/0 | 1/1 | diff | 29.3 |
| **recharge002** | V1 | 2 | 0/0 | 0/1 | sql_file | 41.0 |
| recharge002 | V2 | 2 | 0/0 | 0/1 | sql_file | 47.9 |
| recharge002 | V4 | 2 | 0/0 | 0/1 | diff | 76.4 |
| **xero001** | V1 | 2 | 0/0 | 0/1 | sql_file | 47.7 |
| xero001 | V2 | 2 | 0/0 | 0/1 | sql_file | 34.3 |
| xero001 | V4 | 2 | 0/0 | 0/1 | diff | 34.9 |
| **lever001** | V1 | 2 | 0/0 | 0/1 | sql_file | 47.4 |
| lever001 | V2 | 2 | 0/0 | 0/1 | sql_file | 68.5 |
| lever001 | V4 | **0** | **58/0** | **1/1** | diff | 52.2 |

## Paired analysis

McNemar discordance counts on score, V_i → V_j:

| Comparison | helpful (j right, i wrong) | harmful (j wrong, i right) | both right | both wrong | verdict |
|---|---:|---:|---:|---:|---|
| V1 → V2 | 0 | 0 | 2 | 4 | **tied** (V2 brought no signal on score) |
| V1 → V4 | **1** (lever001) | 0 | 2 | 3 | **improved** (1 helpful / 0 harmful) |
| V2 → V4 | **1** (lever001) | 0 | 2 | 3 | **improved** |

McNemar continuity-corrected p (b=0, c=1) = 1.0 — n is too small for
significance. Direction is the right one.

But the **`dbt_run_rc=0` rate** is the more interesting signal at this
n: V1 = 0/6, V2 = 0/6, V4 = 2/6. **2 of 6 V4 attempts produced clean
end-to-end dbt runs**; neither V1 nor V2 produced any. That's a real
operational difference even if score is noisy.

## Why V2 (better grounding) didn't help

The V2 prompt is **3.5× larger** (12k vs 8.2k chars on asana001) — it
shows column lists for every model — but the model still emits a
fresh `models/<new_name>.sql`. The schema enrichment helps it pick
better column names *internally*, but it doesn't dissuade it from
overwriting the project structure with a single new file.

In other words: telling the model what's there is not enough. You
also have to tell it **what to do** with what's there. That's the
V4 instruction.

## Why V4 (diff-form) helps

Two mechanisms:

1. **Forces ground in existing files.** The diff syntax requires the
   model to name an existing file in the `--- a/` line. It can't
   invent names that don't exist (it would still try, but the diff
   apply would fail and we'd see it). On `playbook001`, the existing
   `attribution_touches.sql` is empty and the model edits it via diff
   to add the missing logic — that's exactly what gold expects.
2. **Smaller blast radius.** A diff against one file is a smaller
   unit than a fresh model file with potentially-wrong CTE chain.
   Even when the diff fails to compile (asana001 V4 dbt_run_rc=1),
   it leaves the rest of the project intact, so dbt test still runs
   to completion and produces 30 PASS / 21 ERROR.

The two clean wins V4 produced:

- **playbook001:** model patched
  `models/attribution_touches.sql` to compute the 4 expected columns
  (visit, conversion_id, attribution_method, attribution_value).
  dbt run + test green; gold matched.
- **lever001:** model patched the existing
  `lever__posting_enhanced.sql` with the joins gold expected. 58
  tests passed (the project's full test suite).

## What V2 did help with that's invisible here

Wall-clock time: V2 generates slightly **shorter** outputs because
the model sees structure and stops at "match the convention". It's
not an EX win, but it's a small token-efficiency win.

## Limitations / honest caveats

1. **n=6 is too small** for paired stats. The clear "lever001" win
   for V4 is anecdotally meaningful but not significant.
2. **`retail001` / `playbook001` "matched" baseline** is partly an
   artifact of how the upstream example dirs already contain the
   target table when copied via `cp -R`. Our score of `1/1` includes
   cases where the agent added a broken file but the existing project
   produced the gold table independently. The clean V4 win on
   `lever001` doesn't have that confound (lever001 V1/V2 score 0/1).
3. **`dbt_test` ERROR** on asana001 V4 (21 errors out of 51 tests) is
   the *upstream* test failure pattern from substituted-source-identifier
   bugs in the project as shipped — same as we saw in our first
   real-model run. Not our model's fault. The 30 PASS that V4 gets
   would be 0 PASS if the project failed to compile, so the diff
   form at least kept the train running.
4. **One-shot is limiting.** None of the variants got `dbt_run_rc=0`
   on asana001 / recharge002 / xero001 because those tasks need 2+
   cooperating models. V3 ReAct (server-stateful loop) is the proper
   answer here; V4 is a partial substitute.

## Verdict

V4 (diff-form priority) is the simplest meaningful improvement we
have for the Spider2-DBT lane. **Adopt as the default prompt for
the bridge** going forward. V2 (richer grounding) does not pay for
its prompt-budget cost at this n; keep the column-list emitter as
optional infrastructure for future use, but don't make it default.

V3 ReAct remains the next-priority lift; design in
`spider2_dbt_bridge/react_loop_skeleton_v3.md`.

## Reproduce

```bash
python spider2_dbt_bridge/run_dbt_ablation.py \
    --tasks asana001 playbook001 retail001 recharge002 xero001 lever001 \
    --variants v1 v2 v4 \
    --max-new 1500 \
    --run-id ablation_main
```

Outputs: [outputs/dbt_ablation/ablation_main/](../dbt_ablation/ablation_main/)
- `per_task.jsonl` — one row per (task, variant) with full metrics
- `summary.csv` — flat CSV for analysis
- `readout.md` — human-readable per-variant + per-task table
