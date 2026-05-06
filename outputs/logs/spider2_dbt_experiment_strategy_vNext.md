# Spider2-DBT vNext Experiment Strategy

_Authored from `experiments/denis` HEAD = `8f57eea`. Treats the prior
ablation V1/V2/V4 (n=6) as the freshest empirical anchor and the
cumulative Phase 1–10 history as the architectural prior. This is a
research plan, not implementation; nothing here triggers heavy runs._

## 1. Executive summary

1. **Track priority is fixed: DBT-first, then BigQuery, then Snowflake, then SQLite.** DBT is the only track where the lane is technically alive end-to-end (bridge + official evaluator + smoke green) and the benchmark is small (68 tasks). Snowflake is infrastructurally blocked (0/58 dbs). BigQuery exec_ok already crossed 45% but EX is stuck near 2% because the bottleneck moved from execution to reasoning. SQLite is non-comparable on sample data.
2. **V4 (diff-form priority) is the freshest empirical winner** for the DBT lane: 2/6 dbt_run_rc=0 vs 0/6 for V1/V2; 3/6 matched vs 2/6. Adopt as default prompt **for the prompt layer only**; the bigger win must come from architecture, not from one more prompt rewrite.
3. **V2 (richer grounding) did not pay for its prompt-budget cost** at n=6. Adding column lists is necessary but not sufficient — the model needs *what to do* with the structure, not more bytes describing it.
4. **n=6 is too small for significance** (McNemar p=1.0 even with helpful=1 / harmful=0). All future variants must be evaluated on a stratified dev set (≥20 tasks) with paired stats and a held-out 20–30 to prevent overfitting to lever001 / playbook001 / asana001 / retail001.
5. **`retail001` and `playbook001 v1` are confounded floors**: the upstream example dir, when copied, already contains models that produce the gold-expected table. Score 1/1 with dbt_run_rc=2 (compile fail) on retail001 is a "do-nothing" win. The dev set must include and label these floor cases so the architecture doesn't get credit for them.
6. **The Deep Research line is "repository-level agent, not single-shot SQL."** That implies (a) typed planner / router (Layer 1), (b) dbt-graph-aware retrieval (Layer 2), (c) execution-guided controller with bounded repair + candidate pool + selector (Layer 3). The current bridge already implements Layer 3's executor + repair primitives but uses a one-shot prompt and naive retrieval.
7. **The next leap is not "another reranker" or "wider context window."** Past phases proved that reranker (R2), evidence_semantics (Phase 7), demo retrieval (Phase 8), and planner-model swap (Phase D) did NOT add signal once a strong controller existed. The leverage is in **controlling the agent's action space** via diff-first policy, target-file discipline, and execution feedback — not in adding semantic layers above a still-uncontrolled generator.
8. **DBT is dominated by ONE common failure mode**: the model emits a fresh `models/<new>.sql` when gold expects a small patch to an existing model. V4 partially addresses this; V5 should make it strict via schema-validated action types.
9. **The official Spider2-DBT evaluator is `duckdb_match` over named tables/columns** — this is a row-level binary match (per task), not a soft score. It does not reward "almost right." Therefore the only experiments worth running are ones whose mechanism predicts more *exactly correct* tables.
10. **No gold-leakage in submission mode.** Gold SQL / gold tables can only enter offline diagnostic paths, never the prompt or the candidate generator. Section 7 (no-leakage policy) makes this enforceable.
11. **Reproducibility is non-negotiable**: every experiment writes JSONL + manifest + commit hash + seed; metrics contract (Section 12) freezes the field set so vNext readouts are diffable.
12. **V3 (multi-step ReAct) stays deferred** until single-shot architecture (planner + retrieval + controlled diff + repair + judge) is stable. Free-running ReAct without these foundations multiplies failure modes.
13. **Realistic targets** (see §16): conservative — 20–25% matched on holdout-30; expected — 30–40%; optimistic — ≥45%. Coder-7B is not GPT-4; the official Spider2 paper reports GPT-4 ≈ 6% on full Spider2. Spider2-DBT is structurally easier (smaller surface, official evaluator binary), so we can plausibly exceed GPT-4's number, but we should not chase it.
14. **BigQuery is not abandoned** — its remaining gap (88 items exec_ok_but_rows_mismatch) is the same kind of reasoning problem DBT has. Components proven on DBT (typed planner, output-shape contract checker, candidate pool) should transfer; we just don't lead with BQ because the dev loop is slower and more expensive.
15. **One next prompt only** at the end of this document (Section 18). The roadmap that follows is the sequence we actually intend to execute, but each phase has its own implementation prompt to keep agent context focused.

## 2. Current empirical baseline

### V1 / V2 / V4 ablation summary (n=6)

| Variant | Mechanism | dbt_run_rc=0 | matched score | dbt_pass_total | dbt_err_total | wall_s_avg |
|---|---|---:|---:|---:|---:|---:|
| V1 | single fenced block, free-form | 0/6 | 2/6 (33%) | 0 | 0 | 45.3 |
| V2 | + grouped models + column extraction | 0/6 | 2/6 (33%) | 0 | 0 | 45.5 |
| V4 | + diff-form priority over new files | **2/6** | **3/6 (50%)** | **88** | 21 | 46.0 |

Source: [outputs/dbt_ablation/ablation_main/per_task.jsonl](../dbt_ablation/ablation_main/per_task.jsonl).

### Per-task interpretation

| iid | V1 score | V2 score | V4 score | V1 run_rc | V2 run_rc | V4 run_rc | Honest read |
|---|---:|---:|---:|---:|---:|---:|---|
| asana001 | 0/1 | 0/1 | null | 2 | 2 | 1 | V4 diff applied but compile-failed; eval crashed (rc=255) — diff added cols that don't exist on `asana__task` |
| playbook001 | 1/1 | 1/1 | 1/1 | 1 | 2 | **0** | Floor: existing example already has `attribution_touches` stub. Only V4 compiled cleanly; V1/V2 score 1 by accident (partial dbt run + pre-existing models) |
| retail001 | 1/1 | 1/1 | 1/1 | 2 | 2 | 2 | **Pure floor**: upstream `report_customer_invoices` model exists; agent's add fails to compile but other models run and produce gold. Should not credit any variant. |
| recharge002 | 0/1 | 0/1 | 0/1 | 2 | 2 | 2 | Hard task — none of the variants reached compile. |
| xero001 | 0/1 | 0/1 | 0/1 | 2 | 2 | 2 | Hard task — same. |
| lever001 | 0/1 | 0/1 | **1/1** | 2 | 2 | **0** | **Clean V4 win**: V1/V2 fresh `models/reports/job_report.sql` failed; V4 diff patched `lever__posting_enhanced.sql` correctly, 58 tests passed, gold matched. |

### What `dbt_run_rc=0` actually means and why we track it

`dbt_run_rc=0` is captured from `${PIPESTATUS[0]}` of `dbt run` after `dbt deps`. It means every model in the project (including our addition) compiled and executed without error. This is a strictly stronger signal than `matched score` because:

- Score can be 1 even when our addition broke (retail001 floor).
- Score can be 0 even when our addition ran (gold mismatch).
- `dbt_run_rc=0` cleanly tells us whether our edit was *deployable*.

Both should be tracked separately; neither replaces the other.

### Why V4 wins (mechanism)

1. **Diff syntax forces target naming**: the `--- a/<path>` line names a real file; if it doesn't exist, `git apply` rejects the patch and we see it. New SQL in `models/<invented>.sql` always "succeeds at writing" even when the project has no place for that file.
2. **Smaller blast radius**: a diff that touches one file leaves the rest of the project running. Even when the diff is wrong (asana001 V4), `dbt test` keeps producing 30 PASS — V1/V2's failure-on-compile produces 0 PASS.
3. **Task-structure fit**: many DBT tasks expect a *small addition* to an *existing* model (gold often matches a partially-stubbed file). New-file generation is the wrong primitive for that shape.

### Why V2 didn't help

Showing column lists for every model triples the prompt size but does not constrain the agent's *output*. The model still reaches for `models/<my_choice>.sql` because that's the dominant pattern in its training data ("write a new dbt model for X"). Grounding-without-discipline is bytes wasted.

## 3. Lessons from previous Deep Research (and our own Phase 1–10 history)

| Past finding (commit) | What it says | Implication for vNext |
|---|---|---|
| Phase A retrieval helps on Spider/BIRD (`d2cf0b4`) | Lexical retrieval over schema closes a real gap | DBT retrieval should not be skipped, but lexical alone is too weak — needs graph |
| Phase B planner alone hurts (`98d39e1`) | Plan-then-compile without runtime verification regresses | Planner must be SERVANT to executor, not output-controlling |
| Phase C controller closes Phase B (`adf4415`) | Verifier + non-harm tie-break beats both planner and retrieval-only | Same controller pattern fits DBT: candidate pool + executor as ranker |
| Phase R2 reranker neutral-to-harmful (`6525a94`) | Saturated reranker compresses scores, biases anchor | Don't add a "fancier ranker" before single-candidate quality is fixed |
| Phase D planner swap (`cfcafe3`) | Coder-7B is the best planner in our regime | Don't swap base model unless we change scale dramatically |
| Phase 6 LLM-as-judge new SOTA (`8559379`) | Calibrated judge over candidate pool > heuristic ranker | Judge is the right *final* step, but only after candidates are executable |
| Phase 7 evidence_semantics no-op (`56ec0f3`) | Rich evidence is no-op once gold per-item evidence is in prompt | Don't double-up on context — pick the load-bearing slice |
| Phase 8 demo retrieval tied (`cc245d4`) | DAIL-style demos ≈ B6_v7 on Spider | Few-shot from train pool is not the unlock |
| Phase 10 BQ v8 (`54e060c`) | Multi-candidate + repair raises exec_ok by +24.9pp but EX only +0.49pp | Reasoning gap is now visible; structural fixes are exhausted |

**Net architectural prior**: a stable Spider2 path is *retrieval → bounded planner → candidate pool → executor as ranker → calibrated judge*. The DBT lane needs the same skeleton, with execution feedback as the central scoring signal and diff-form as the safe action primitive.

## 4. Target architecture

### Layer 1 — Task Understanding & Routing (typed planner)

| Field | Spec |
|---|---|
| **Purpose** | Convert NL question + dbt project into a structured action contract before any SQL is written. |
| **Input** | `instruction`, list of existing models (paths + summary), list of sources, gold artifact name pattern. NO gold SQL. |
| **Output** | Strict JSON: `{action_type, target_file, allowed_dependencies, expected_output_columns_n, expected_grain, acceptance_checks, confidence, rationale_short, missing_context}`. |
| **Action types** | `patch_existing_model`, `fill_stub_model`, `create_new_model`, `fix_ref_or_source`, `edit_schema_yml`, `unsupported`. Distribution of types is enforced by the candidate generator (Layer 3 only emits a candidate if the planner's action_type permits it). |
| **Failure modes** | (a) JSON parse fail → fall back to V4 default; (b) wrong target file → executor catches via `git apply` failure; (c) over-eager `create_new_model` when patch suffices → addressed by candidate diversity. |
| **Metrics** | planner_parse_ok, planner_action_distribution, planner_target_match (planner-named file vs file actually edited), planner_overrode_count. |

### Layer 2 — Context Builder (graph-aware retrieval)

| Field | Spec |
|---|---|
| **Purpose** | Build a focused prompt pack from the dbt project graph + DuckDB schema. |
| **Input** | task_id, planner output, full project tree. |
| **Output** | Prompt pack: `target_model_body` (full text), `1-hop neighbors via {{ ref() }}` (full body), `2-hop neighbors` (signature only), `relevant schema.yml fragment`, `DuckDB schema slice for sources used`, `failing_test_summary` (if any), `recent_run_log_summary` (if from prior repair iteration). |
| **Retrieval signals** | (1) BFS over `ref/source` edges from planner's `target_file`; (2) lexical BM25 over question terms × column names; (3) entity overlap (proper nouns in question vs model names); (4) macro/package usage hints; (5) any stub/empty bodies (high-priority targets). |
| **Failure modes** | (a) over-pruned context → planner can request expansion; (b) over-included context → enforced char budget; (c) wrong target_file → executor rejects, controller falls back. |
| **Metrics** | context_pack_chars, n_neighbors_1hop, n_neighbors_2hop, target_file_in_pack (must be true), retrieval_fallback_used. |

### Layer 3 — Execution-Guided Controller

| Component | Spec |
|---|---|
| **Candidate generator** | Up to 4 candidates per task (configurable), each tagged with action_type from planner. Diff-first policy: at most 1 candidate of `create_new_model` type unless planner explicitly chose it. |
| **Executor** | Per-candidate fresh workspace (cp -R copy-on-write). `dbt deps && dbt run && dbt test`. rc and pass/err counts captured. |
| **Error classifier** | Maps stderr/stdout to taxonomy bucket (Section 9). Used to gate repair (some buckets unrepairable, some repairable). |
| **Repair controller** | Bounded N rounds (default 1; up to 2 only for repairable buckets). Re-emit candidate with the exact dbt error in prompt. |
| **Selector / judge** | Hard filters (compile fail, no target file, blast radius too big) → drop. Soft scores (test pass count, patch minimality, planner contract match) → rank. LLM judge fires only when ≥2 *executable* candidates remain and margin is small. |
| **Trajectory logger** | One JSONL row per candidate per round with full state, plus a final `result.json` with selected candidate + metrics + version stamps. |

### What's already built vs what's missing

| Component | Status |
|---|---|
| Bridge transport (SSH/scp + Colab inference) | ✅ committed (`af8d411`) |
| Per-task isolated workspace, cp -R | ✅ committed (`af8d411`) |
| `dbt deps && dbt run && dbt test` runner with rc capture | ✅ committed (`af8d411`) |
| Official `evaluate.py` wrapper | ✅ committed (`16345f9`) |
| V4 diff-form prompt | ✅ committed (`8f57eea`) |
| Multi-variant orchestrator (paired runs) | ✅ committed (`8f57eea`) |
| Typed planner | ❌ to build (Phase 3) |
| Graph index of dbt project | ❌ to build (Phase 4) |
| Retrieval-conditioned context | ❌ to build (Phase 4) |
| Multi-candidate generation per task | ❌ to build (Phase 6) |
| Error classifier + repair controller | ❌ to build (Phase 5) |
| Selector / judge over executable candidates | ❌ to build (Phase 6) |
| ReAct multi-step (V3) | 🅟 designed (`react_loop_skeleton_v3.md`), implementation deferred |

## 5. DBT experiment roadmap

Each phase is an isolated PR-sized unit with its own success/rollback criteria. **No phase blocks itself by requiring later-phase components.**

### Phase 0 — Audit, baseline freeze, taxonomy

| Field | Spec |
|---|---|
| Objective | Lock current numbers; tag dev/holdout split; produce error taxonomy with concrete examples. |
| Tasks | (a) freeze `outputs/dbt_ablation/ablation_main` as the V4 baseline; (b) classify each of the 68 tasks into the taxonomy of Section 8; (c) produce a stratified `dev_20` and a held-out `holdout_30` (sec 14); (d) add a `floor_marker` column flagging items where the upstream example produces the gold table without any agent edit (retail001 case). |
| Success criteria | `outputs/spider2_dbt/dev_holdout_split.json` with stratification stats; `outputs/spider2_dbt/task_taxonomy.csv`; `outputs/spider2_dbt/floor_baseline.json` (do-nothing score on each task). |
| Rollback criteria | Any taxonomy bucket has < 3 examples or > 25 examples → reclassify before continuing. |
| Cost | Zero LLM cost; ≈ 1 hour of human review. |

### Phase 1 — Floor + V4 sanity on dev_20

| Field | Spec |
|---|---|
| Objective | Establish do-nothing floor and current V4 score on `dev_20`. Determine if reported V4 gain holds at larger n. |
| Tasks | Run `--variants v4` and `--variants v0_floor` (no agent edit; just `cp -R + dbt run + eval`) on `dev_20`. |
| Success criteria | V4 score > floor by at least 1 helpful / 0 harmful item with no McNemar regression. |
| Rollback criteria | V4 ties floor → escalate: the prompt-only gains were noise; jump to Phase 3 (planner) sooner. |
| Cost | 20 × 2 variants × ~50s ≈ 35 min runtime. |

### Phase 2 — V4 + stricter target-file policy (V5)

| Field | Spec |
|---|---|
| Objective | Test whether forcing diff-form to name an existing target file (and refusing fallback to fresh SQL) tightens the win. |
| Hypothesis | Models that emit fresh files when a patch would suffice are responsible for most V4 dbt_run_rc≠0 cases. |
| Mechanism | V5 prompt: "you MUST emit a unified diff against ONE of the listed existing model files. If the task requires a brand-new model, emit a special tag `<<NEW_FILE>>` and we'll handle it separately." Apply step refuses fresh SQL outside the tag. |
| Risk | Some tasks genuinely need new files (e.g., recharge002 → `recharge__customer_daily_rollup` doesn't exist). False refusals will lower score on those. Mitigated by the explicit tag. |
| Stopping criterion | If V5 ≥ V4 with paired McNemar harmful=0, adopt; otherwise revert. |

### Phase 3 — Typed planner / router (V6)

| Field | Spec |
|---|---|
| Objective | Insert a planner step before generation; route action to one of {patch_existing, fill_stub, create_new, fix_ref, edit_yml}. |
| Mechanism | Planner LLM call returns strict JSON. Prompt for the SQL generator now sees `target_file` + `action_type` + `expected_output_columns_n` + `acceptance_checks`. |
| Risk | Phase B taught us planner-only hurts. We must keep the executor as the final ranker, not the planner. Planner output is *a hint*, not authority. |
| Stopping criterion | V6 ≥ V5 on `dev_20` paired; planner_parse_ok ≥ 90%. |

### Phase 4 — Graph-conditioned retrieval (V7)

| Field | Spec |
|---|---|
| Objective | Replace flat file-listing with BFS-derived neighbor pack centered on the planner's target_file. |
| Mechanism | Build dbt manifest graph from `dbt parse`; for each task, retrieve k=4 1-hop neighbors and k=8 2-hop summaries; include relevant schema.yml fragment; cap at 6000 chars. |
| Risk | Wrong target_file from planner → wrong neighborhood → worse than flat. Mitigated by including a small "global" budget (top-3 lex matches) as backup. |
| Stopping criterion | V7 ≥ V6 with target_file_in_pack ≥ 95%. |

### Phase 5 — Execution-guided repair loop (V8)

| Field | Spec |
|---|---|
| Objective | Add bounded repair (N=2) using the actual dbt error message. |
| Mechanism | If `dbt run` rc≠0, classify error, prompt LLM with the error (no extra context expansion in round 1; expanded in round 2 if first repair also fails). |
| Risk | Repair can degrade by chasing irrelevant changes. Mitigated by patch-minimality penalty (large delta in repair → -score). |
| Stopping criterion | Helpful (V8 right, V7 wrong) > harmful by paired count. |

### Phase 6 — Candidate pool + selector (V9, V10)

| Field | Spec |
|---|---|
| Objective | Generate up to 4 candidates with mixed action types; rank by hard filters then soft scores; optional LLM judge. |
| Mechanism | Same as BQ v8 multi-candidate, but with diff-first policy and per-candidate fresh workspace. |
| Risk | Cost: 4× inference per task. Pre-budget for `dev_20`: 4 × 20 × ~30s = 40 min per ablation. Acceptable for `dev_20`, gated on `holdout_30`. |
| Stopping criterion | V9/V10 ≥ V8 with helpful > harmful at p < 0.10 (sign test). |

### Phase 7 — Full 68 DBT run

| Field | Spec |
|---|---|
| Objective | Final reportable number on the full benchmark. |
| Tasks | Run the winning variant from Phase 6 on all 68 tasks, plus floor + V4 baselines for paired comparison. |
| Success criteria | Bootstrap CI on score is reportable; per-task error taxonomy distribution generated; failure-mode plot ready. |
| Rollback criteria | If full-68 score is materially worse than dev_20 (Δ > 10 pp absolute), STOP, audit for dev/holdout leakage, do not finalize. |

### Phase 8 — BigQuery transfer

Take the planner + output-shape contract checker + per-candidate diff policy from DBT, port to A_bq lane. Specifically: the planner's `expected_output_columns_n` and `expected_grain` become BQ result-shape pre-checks before official EX comparison. Goal: lift BQ EX from 2.45% toward 10%.

### Phase 9 — Snowflake (after dbs unblock)

The SF executor / schema_index / prompting / agent are all committed (`16345f9`). Work resumes when xlang-ai grants the Marketplace share or a us-west-2 account is created. Until then, only `probe_databases.py` runs occasionally to detect attached shares.

### Phase 10 — SQLite

Stays as a cheap inference sandbox; do not lead with it for the diploma scoring story (non-comparable on sample data).

## 6. Ablation matrix

See [outputs/logs/spider2_dbt_experiment_matrix_vNext.md](spider2_dbt_experiment_matrix_vNext.md) for the full table with hypotheses, expected mechanisms, risks, metrics, run commands, and falsification criteria for V1–V10. Each entry is paired against its immediate predecessor (V_n vs V_{n-1}) on the same task set.

## 7. Task taxonomy

See [outputs/logs/spider2_dbt_task_taxonomy_plan.md](spider2_dbt_task_taxonomy_plan.md). 13 buckets, with detection rules, expected solution patterns, common failure modes, and best prompt policy per bucket. Phase 0 produces a per-task labeling.

## 8. Error taxonomy

Compile / run / test / official-eval errors mapped to repair actions and stop criteria. Embedded in the metrics contract (Section 12) so every variant's `result.json` carries an `error_bucket` field consumable by paired analysis. Also see Section 9 of `spider2_dbt_metrics_contract.md`.

## 9. Context / retrieval strategy

| Layer | What's included | When it's added |
|---|---|---|
| L0 always | `dbt_project.yml` head, `profiles.yml` head, `packages.yml` | every prompt |
| L1 always | full body of planner-named `target_file` (or empty if doesn't exist yet) | every prompt |
| L2 always | 1-hop `{{ ref() }}` neighbors (full body, max 4) | Phase 4+ |
| L3 conditional | 2-hop neighbors (signature only, max 8) | Phase 4+ |
| L4 conditional | relevant `schema.yml` fragment (the model's tests / columns block) | Phase 4+ |
| L5 conditional | DuckDB schema slice for sources actually referenced | every prompt |
| L6 only on repair | dbt error message (verbatim) | Phase 5+ |
| L7 only on repair round 2 | full `dbt_run.log` tail (last 2000 chars) | Phase 5+ |

Char budget caps: L0+L1 = 2000, L2+L3 = 3500, L4+L5 = 1500, L6+L7 = 1500. Total ≤ 8500 chars (leaves room for system rules + question + output expectations within the 14k cap).

Ablations within Phase 4: lexical-only vs graph-only vs both; with vs without schema.yml; with vs without prior-run log.

## 10. Candidate generation strategy

| Setting | Default |
|---|---|
| Max candidates per task | 4 (Phase 6+); 1 (Phase 0–5) |
| Action-type distribution | ≤1 of `create_new_model`, ≤2 of `patch_existing_model`, ≤1 of `fill_stub_model` per task |
| Patch size budget | ≤ 80 lines added/removed per diff |
| Schema.yml edits | Allowed only when planner action_type is `edit_schema_yml` |
| Macro/config edits | Allowed only when planner action_type is `unsupported` and forwarded to a separate path |
| Per-candidate workspace | Always fresh `cp -R` from upstream — never share state |
| No gold-leakage | Hard policy (Section 7 in metrics contract) |

## 11. Execution-guided repair strategy

| Setting | Default |
|---|---|
| Max repair rounds | 2 |
| Round-1 trigger | dbt_run_rc ≠ 0 with classified bucket ∈ {syntax, missing_ref, missing_column, type_mismatch} |
| Round-2 trigger | round-1 also failed and classified bucket changed (avoid loops) |
| Termination | round-2 also fails OR new bucket = `permission_denied` / `package_install_failed` (unrepairable) |
| Anti-regression | If repair makes patch larger than 1.5× original AND still fails, prefer original |

## 12. Selector / judge strategy

Hard filters (drop candidate immediately):
- `dbt_apply_rc != 0` (patch didn't even apply)
- `dbt_run_rc != 0` AND no repair candidate succeeded
- `target_file` not in project AND action_type ≠ `create_new_model`
- patch size > 80 lines without explicit `edit_schema_yml` justification
- gold-leakage detected (statics matching gold table contents in patch body — sec 7 of no-leakage policy)

Soft scores (rank survivors):
- (`dbt_run_rc=0`) ⇒ +3
- (`dbt_test pass_n` per total tests) ⇒ +1 × ratio
- (planner contract match: target_file matches planner's choice) ⇒ +1
- patch minimality (smaller diff for a given pass count) ⇒ + small bonus
- candidate confidence (model logprob, if exposed) ⇒ + small

LLM judge fires only when ≥2 candidates have `dbt_run_rc=0` and their soft scores are within 0.5 of each other. The judge sees the question + each candidate's diff + each candidate's tests-pass summary; it does NOT see gold.

Hard rule: judge cannot overrule a hard filter.

## 13. BigQuery transfer plan

Once the DBT controller is stable, port to A_bq lane:
1. Reuse the planner with action_type adapted: `select_only`, `cte_decomp`, `joined_with_unnest`.
2. Add an output-shape pre-check: planner declares `expected_output_columns_n` and `expected_grain`; before official EX comparison, we check the predicted query's shape via `LIMIT 0` schema introspection. Mismatched shape → repair with explicit shape hint.
3. Reuse candidate pool + judge.
4. Goal: lift BQ EX from current 2.45% toward 10% (conservative) / 15% (expected). Mechanism: ~88 items in `exec_ok_but_rows_mismatch` bucket are exactly the ones a planner+shape-checker would catch.

## 14. Snowflake plan

Until shares are attached: only `probe_databases.py` and the readiness gate. No prompt iteration on SF tasks; engineering effort goes to DBT. After unblock, the SF agent (already wired) reuses BQ's planner + shape checker.

## 15. SQLite plan

Cheap sandbox for prompt-iteration smoke tests where API/exec cost matters. Do not include SQLite numbers in the diploma's main scoring narrative.

## 16. Realistic targets

| Bucket | Conservative | Expected | Optimistic |
|---|---:|---:|---:|
| DBT compile rate (dbt_run_rc=0) on dev_20 | 25% | 40% | 55% |
| DBT matched score on dev_20 | 25% | 35% | 45% |
| DBT matched score on holdout_30 | 20% | 30% | 40% |
| DBT matched score on full 68 | 18% | 28% | 38% |
| BQ EX on A_bq 205 (Phase 8) | 4% | 7% | 12% |
| Snowflake (after share) | n/a | n/a | n/a |

These are honest *plausible* bands, not promises. Coder-7B is not GPT-4 (Spider2 paper reports GPT-4 ≈ 6% on full Spider2). Spider2-DBT is structurally easier than Spider2-Lite-SF/BQ because the official evaluator is binary on named tables, not row-level over enterprise warehouses; we expect to exceed GPT-4's 6% on DBT specifically, but not by a huge margin without a stronger base model.

## 17. Reproducibility and reporting

Every variant run produces:
- `outputs/dbt_<variant>/<run_id>/per_task.jsonl` — one row per task with the full metric contract (sec 12 of metrics doc)
- `outputs/dbt_<variant>/<run_id>/summary.csv` — flat table for paired analysis
- `outputs/dbt_<variant>/<run_id>/readout.md` — human-readable variant report
- `outputs/dbt_<variant>/<run_id>/manifest.json` — variant config, model id, prompt template hash, commit hash, seed, wall-clock start/end
- For each task: per-candidate `result.json` and `model_response_<variant>.txt` retained; workspace tar collected on demand

The metrics contract (Section 12 doc) is the single source of truth for field names. Variant readouts must conform.

## 18. Immediate next implementation prompt

See [outputs/logs/spider2_dbt_next_implementation_prompt.md](spider2_dbt_next_implementation_prompt.md). The prompt is scoped to **Phase 0 only**: produce the dev/holdout split + task taxonomy labeling + floor baseline. No heavy LLM calls; pure analysis and labeling work.
