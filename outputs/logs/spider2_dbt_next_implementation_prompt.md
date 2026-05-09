# Next implementation prompt — Phase 0 (taxonomy + dev/holdout split + floor)

_Self-contained prompt for the next agent. Scoped to Phase 0 only.
Single concrete next step. No heavy LLM runs._

---

## Task for the next agent

Branch: `experiments/denis`. HEAD must be at or after `8f57eea`.

You are running Phase 0 of the Spider2-DBT vNext experiment program.
The strategy / matrix / taxonomy / metrics contract / no-leakage policy
were committed in the prior turn (see commit "Add Spider2 DBT vNext
experiment strategy"). Read them once before doing anything:

- `outputs/logs/spider2_dbt_experiment_strategy_vNext.md`
- `outputs/logs/spider2_dbt_experiment_matrix_vNext.md`
- `outputs/logs/spider2_dbt_task_taxonomy_plan.md`
- `outputs/logs/spider2_dbt_metrics_contract.md`
- `outputs/logs/spider2_dbt_no_leakage_policy.md`

Phase 0 has FOUR concrete deliverables. Build them in order; each
unlocks the next.

### Deliverable 1 — Per-task taxonomy labeling

File to produce: `outputs/spider2_dbt/task_taxonomy.csv`
Schema: see "Phase 0 deliverable" in the taxonomy plan
(`spider2_dbt_task_taxonomy_plan.md`):
```
instance_id, gold_target_table, primary_bucket, secondary_buckets,
upstream_compile_ok, upstream_test_pass, upstream_test_fail,
floor_score, v4_score, notes
```

How:

1. SSH to the server (passwordless from the local box; see
   `spider2_dbt_bridge/ssh_utils.py`).
2. For each of 68 instance_ids in
   `vendor/Spider2/spider2-dbt/examples/spider2-dbt.jsonl`:
   - read the instruction
   - read the gold spec from `evaluation_suite/gold/spider2_eval.jsonl`
     (this is allowed for Phase 0 labeling — it's a one-time offline
     analysis output, NOT a submission-flow input; tag the labeling file
     as Mode B per `spider2_dbt_no_leakage_policy.md`)
   - inspect the upstream `examples/<iid>/` directory layout via SSH
   - apply the detection rules from each taxonomy bucket (in order, first
     match wins)
   - record `primary_bucket`, plus any `secondary_buckets` that also fit
   - record `gold_target_table` from gold's `condition_tabs[0]`
   - record `target_file_existed_in_upstream` (does
     `examples/<iid>/models/<target>.sql` exist?)
3. Use the heuristic ranking script `spider2_dbt_bridge/server_side/analyze_tasks.py`
   for fast per-task triage; the actual bucket label still requires reading
   the example dir.

DO NOT call the LLM for this step. Pure file-system + JSON work.

Required quality: every task gets exactly one `primary_bucket`. If you
honestly cannot decide, mark as `unclear` and add a one-sentence note.

### Deliverable 2 — Floor baseline (V0)

File to produce: `outputs/spider2_dbt/floor_baseline.json` and
`outputs/dbt_ablation/floor/per_task.jsonl`.

How:

1. Add a `--variants v0_floor` branch to `spider2_dbt_bridge/run_dbt_ablation.py`.
   In this branch, SKIP inference and SKIP apply. Just `cp -R` the upstream
   example into the per-task workspace and run `dbt deps && dbt run && dbt test`,
   then call `server_official_eval.py`.
2. Run on all 68 tasks (small cost — no LLM).
3. Output the same per-task fields as a regular variant (per the metrics
   contract), with `apply_kind: "none"` and empty `pushed_files: []`.

Important: this is the do-nothing floor. Tasks where the upstream already
produces the gold table will score 1/1 here; flag them in the taxonomy
CSV as `floor_marker: "upstream_already_produces_gold"`. They MUST NOT
contribute to any future variant's "matched" claim — strip them in
paired comparison.

### Deliverable 3 — Stratified dev/holdout split

File to produce: `outputs/spider2_dbt/dev_holdout_split.json`.

How:

1. Read `task_taxonomy.csv` and `floor_baseline.json`.
2. Build three sets:
   - `smoke`: the 6 tasks already used in `ablation_main`
     (asana001, playbook001, retail001, recharge002, xero001, lever001).
   - `dev_20`: 20 tasks, stratified across taxonomy buckets per the
     policy in the taxonomy plan. Avoid all 6 smoke tasks. Avoid
     `upstream_broken` and `upstream_already_produces_gold` floor cases
     where possible (some are fine to keep for negative cases).
   - `holdout_30`: 30 tasks NOT in smoke ∪ dev_20. Same stratification
     rules. The remaining 12 tasks (68 − 6 − 20 − 30) become an unused
     reserve.
3. Verify stratification: write a `stratification_check` block in the
   JSON listing per-bucket counts in each split.

Stratification policy reminder:
- each bucket's representation in `dev_20` should be ≥ 1 if the bucket
  has any item, and ≥ 2 if it has ≥ 4 items in the full set.
- `holdout_30` should have ≥ 50% of every bucket present in `dev_20`.

### Deliverable 4 — V4 vs V0_floor on dev_20

File to produce: `outputs/dbt_ablation/v4_vs_floor_dev20/`
(per_task.jsonl, summary.csv, readout.md, paired_v0_floor_vs_v4.csv).

How:

1. Run `run_dbt_ablation.py --variants v0_floor v4 --tasks <dev_20 list>
   --run-id v4_vs_floor_dev20 --max-new 1500`.
2. Generate paired comparison CSV (use the schema in metrics contract).
3. Write a 1-page readout summarizing:
   - per-bucket score for V0 vs V4
   - count of helpful (V4 right, V0 wrong) — these are the items where
     the agent actually contributed
   - count of harmful (V0 right, V4 wrong) — items where the agent
     broke an upstream that produced gold for free
   - net effect = helpful − harmful
   - any taxonomy bucket where V4 cannot beat V0 — those need a different
     prompt policy in later phases

This is the FIRST honest read of V4's contribution after stripping the
floor confound.

### What you MUST NOT do in Phase 0

- Do not implement V5 / V6 / V7 / V8 / V9 / V10. Those are later phases.
- Do not modify the upstream `vendor/Spider2/spider2-dbt/examples/`.
- Do not feed gold information into any submission-flow code path.
- Do not run heavy multi-candidate inference (4× cost).
- Do not commit `.env`, secrets, or any credentials.
- Do not skip the no-leakage check.

### Commit policy

After Phase 0 deliverables land:

1. `git add outputs/spider2_dbt/ outputs/dbt_ablation/floor/
   outputs/dbt_ablation/v4_vs_floor_dev20/
   spider2_dbt_bridge/run_dbt_ablation.py
   tools/check_no_leakage.py
   tools/check_metrics_contract.py`
2. Verify with `python tools/check_no_leakage.py`.
3. Commit with title:
   `Spider2-DBT Phase 0: taxonomy, dev/holdout split, V0 floor, V4 vs floor on dev_20`
4. Body: aggregate numbers (matched / dbt_run_rc=0) for V0 and V4,
   plus per-bucket helpful/harmful counts.

### Final report after Phase 0

Append a short section to `outputs/REPORT_ALL_SPIDER2_TRACKS.md` titled
"Phase 0 readout" with:
- bucket distribution
- floor coverage (how many of 68 are floor wins)
- V4 net contribution = helpful − harmful on dev_20
- next phase decision: if V4 net ≥ 3, proceed to Phase 2 (V5 strict
  target-file). If V4 net is 0 or negative, jump to Phase 3 (planner)
  earlier than planned because the prompt-only ceiling is reached.

---

That's Phase 0. After this, the next prompt (Phase 1 / Phase 2) is
written based on what V4-vs-floor actually reveals.
