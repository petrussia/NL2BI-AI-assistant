# Spider2-DBT vNext ablation matrix V1 → V10

_All variants paired against their immediate predecessor on the same
task set (dev_20 first, then holdout_30, then full 68). Variant lineage
is intentionally additive: each row only changes ONE thing relative
to the previous so attribution is clean._

| ID | Name | Mechanism (changed component) | Hypothesis | Expected effect | Risk | Falsification | Metric of record | Run command sketch | Artifact dir |
|---|---|---|---|---|---|---|---|---|---|
| **V0** | Floor (no agent) | Skip generation. Just `cp -R` + `dbt run` + `dbt test` + `evaluate.py`. | Some tasks score 1/1 from upstream alone (retail001 case). | Identifies confounds. | None — pure baseline. | If V0 ≥ V4: prior win was floor confound. | matched_count, dbt_run_rc | `run_dbt_ablation.py --variants v0_floor` | `outputs/dbt_ablation/<run_id>/v0_floor/` |
| **V1** | Single-shot baseline | Current `build_model_prompt.py`. | Single fenced block, free naming. | Reference point. | None — incumbent. | n/a | matched_count, dbt_run_rc | `--variants v1` | `outputs/dbt_ablation/<run_id>/v1/` |
| **V2** | Better grounding | + grouped models by class + extracted column lists. | More schema visibility raises matched. | +0–5 pp matched. | Bigger prompt, slower wall clock. | If matched ≤ V1 and prompt > 1.3× larger. | matched_count, prompt_chars | `--variants v2` | `outputs/dbt_ablation/<run_id>/v2/` |
| **V4** | Diff-form priority | Output rule: prefer unified diff against existing file; new file only if no fit. | Forces grounding via existing-file naming + smaller blast radius. | +1–3 helpful items vs V1 on diverse n=20. | Some tasks legitimately need new files; over-strict diff = false refusals. | If V4 < V1 with helpful=0 / harmful≥2. | matched, dbt_run_rc, helpful/harmful | `--variants v4` | `outputs/dbt_ablation/<run_id>/v4/` |
| **V5** | Strict target-file policy | V4 + apply step REFUSES fresh SQL outside an explicit `<<NEW_FILE>>` tag. | Enforce diff form structurally, not just rhetorically. | Lift dbt_run_rc=0 by another +2–4 items by removing model's escape hatch. | Tasks needing new files fail unless tag flow works. | If V5 < V4 with new harmful items in `create_new_model` taxonomy bucket. | dbt_run_rc=0 rate, action_type distribution | `--variants v5` | `outputs/dbt_ablation/<run_id>/v5/` |
| **V6** | + Typed planner | Pre-step LLM call returns JSON `{action_type, target_file, expected_output_columns_n, ...}`. Generator sees these. | Planner anchors target file; generator stops drifting. | +2–5 helpful matched on dev_20. Mostly via target_file match rate. | Phase B teaches planner-only hurts. Mitigation: planner is hint, executor is ranker. | If matched ≤ V5 AND planner_target_match ≥ 80%. | matched, planner_parse_ok, planner_target_match | `--variants v6 --planner` | `outputs/dbt_ablation/<run_id>/v6/` |
| **V7** | + Graph retrieval | Replace flat file listing with BFS-derived neighborhood centered on planner's target_file. | Better context within same budget. | +1–3 matched, larger gain on tasks needing 2+ refs. | Wrong target_file → wrong neighborhood → worse. Mitigation: keep small global pool. | If matched ≤ V6 AND target_file_in_pack ≥ 95%. | matched, target_file_in_pack, n_neighbors | `--variants v7 --graph` | `outputs/dbt_ablation/<run_id>/v7/` |
| **V8** | + Repair loop (N=2) | If `dbt_run_rc≠0`, classify error, re-emit with error in prompt. | Catches dialect typos / wrong column names. | +2–4 dbt_run_rc=0; +1–2 matched. | Repair can chase irrelevant changes. Mitigation: patch-minimality penalty. | If repair_helpful_n < repair_harmful_n. | dbt_run_rc=0 rate, repair_used / repair_success | `--variants v8 --repair=2` | `outputs/dbt_ablation/<run_id>/v8/` |
| **V9** | + Multi-candidate (k=4) | 4 candidates per task, mixed action types, fresh workspace per candidate. | Diversity hedges single-shot bias. | +1–3 matched. Cost: 4× inference. | Cost on full 68 is significant. Gate to dev_20 only until proven. | If matched ≤ V8 AND wall_s ≥ 4× V8. | matched, candidate_count, selected_action_type | `--variants v9 --candidates=4` | `outputs/dbt_ablation/<run_id>/v9/` |
| **V10** | + LLM-as-judge | When ≥2 candidates have `dbt_run_rc=0` with close soft scores, judge picks via question+diff+test-summary. | Selector calibration above heuristic ranker (Phase 6 BIRD pattern). | +0–2 matched on close-call items. | Judge can override correct heuristic; Phase R2 saturation lesson. | If judge_overrode_helpful ≤ judge_overrode_harmful. | matched, judge_invoked, judge_overrode | `--variants v10 --judge` | `outputs/dbt_ablation/<run_id>/v10/` |
| **V3** | (deferred) ReAct loop | Server-stateful step machine; up to 8 steps; action vocabulary {write_file, edit_file, list_models, read_file, dbt_run, dbt_test, terminate}. | Multi-step solves tasks needing 2–4 cooperating models. | +5–10 matched on hard tasks. | Loops can chase irrelevant edits; cost can balloon. | Implementation deferred until V8/V9 ceiling is reached. | matched on hard-task subset, steps_used | `--variants v3 --max-steps=8` | `outputs/dbt_ablation/<run_id>/v3/` |

## Statistical-test policy

- **Primary metric**: `matched_count` (binary per task). Paired McNemar between V_n and V_{n-1} on the same task set.
- **Secondary metric**: `dbt_run_rc=0` rate. Paired McNemar.
- **Additional**: `dbt_test_pass_total` per variant on dev_20 (continuous, paired t-test or Wilcoxon).
- **n thresholds**:
  - dev_20: report effect direction; do not claim significance unless p ≤ 0.10.
  - holdout_30: report p ≤ 0.05 only.
  - full 68: bootstrap 95% CI, report McNemar p, *and* effect size (helpful − harmful).
- **No cherry-picking**: a variant fails if it loses on `dev_20`. We don't promote to `holdout_30` based on a single win on a single task.

## Paired design

For every (variant_a, variant_b) comparison:
- same task set
- same model checkpoint and seed
- same workspace template (cp -R from upstream)
- same dbt deps cache (no extra package installs)
- same evaluator binary

Per-task discordance class:
- both matched: `tied_match`
- a matched, b miss: `harmful_for_b`
- b matched, a miss: `helpful_for_b`
- both miss: `tied_miss`

Promote variant_b only when `helpful_for_b - harmful_for_b ≥ 1` AND no harmful item is in a critical taxonomy bucket (e.g. losing a `create_new_model` task by V5's tag-only policy is a critical regression).

## Smoke / dev / holdout / full schedule

| Stage | Tasks | When variant is promoted from |
|---|---|---|
| Smoke | 6 (asana001, playbook001, retail001, recharge002, xero001, lever001) | always |
| dev_20 | 20 (stratified across taxonomy buckets — Phase 0 produces this) | matched on smoke ≥ predecessor |
| holdout_30 | 30 (held out, never seen during prompt iteration) | promoted variant on dev_20 with helpful>harmful |
| full 68 | 68 | one final run with the winning chain, paired vs floor and V4 |

## What we save per run

For every (variant, task):
- `model_response.txt` — verbatim LLM output
- `apply_manifest.json` — what we shipped: kind, files, fenced block count, target_file, patch_size, action_type
- `dbt_logs/{deps,run,test}.log` — full
- `result.json` — metrics contract fields (sec 12 of metrics doc), matched score, official_eval_rc, error_bucket
- `workspace_snapshot.tgz` (collected on demand for failure analysis)

For every variant run:
- `manifest.json` — config + commit hash + seed + wall-clock + cost summary
- `per_task.jsonl` — one row per task
- `summary.csv` — flat
- `readout.md` — human-readable

## Cost budget

Per-task on Coder-7B / L4:
- inference: ~10–30s
- apply: <5s
- dbt deps + run + test: ~30–60s
- official_eval: ~5s
- total: ~50–100s

Variant cost on dev_20: ~25 min single-candidate; ~100 min for V9 (k=4).
Variant cost on full 68: ~85 min single; ~340 min for V9.

V9/V10 are gated to one run on dev_20 + one run on holdout_30 + one run on full 68 — not iterated.
