# Internal Phase Reports — Index and Provenance

This file indexes every internal artefact the dossier rests on: phase reports, audit logs, sequential-runner outputs, snapshot tarballs, and ad-hoc diagnostic memos. The intent is to make the dossier's claims auditable — every external claim cites this master index, which in turn names the exact file (or directory) on disk and the commit at which it was created.

External references — published papers, leaderboards, dataset papers — are in [01_research_dossier_references.md](01_research_dossier_references.md). Software and tooling artefacts in [03_tooling_and_software.md](03_tooling_and_software.md). Dataset version tags in [04_datasets_and_benchmarks.md](04_datasets_and_benchmarks.md).

## 1. Layout convention

Internal artefacts live in three roots:

* `outputs/REPORT_SPIDER2_V*.md` — narrative phase reports written at the close of each phase, one per phase or sub-phase.
* `outputs/logs/` — scientific-finding logs, negative-result analyses, and per-phase audit memos.
* `outputs/snowflake/`, `outputs/bigquery/`, `outputs/spider1/`, `outputs/bird/`, `outputs/dbt/` — per-engine result directories with `predictions.jsonl`, `traces.jsonl`, `metrics.json`, and `_DONE` files at the leaf level.

The reports referenced in the dossier are listed below by phase. Each entry gives the canonical path, the phase number it documents, the git commit at which it was finalised, and a one-line note on which dossier claim it underpins.

## 2. Phase reports

### 2.1 Pre-Spider 2 era (Phases 1–14)

These phases focused on Spider 1 and BIRD; the per-phase reports were short and have been consolidated into the early-phases narrative.

* `outputs/REPORT_SPIDER1_BIRD_PHASE1_TO_14.md` — consolidated narrative of v1 through v14 covering schema-link introduction (v7), emitter swap (v12), and validator-feedback retry (v14). Underpins [06_EXPERIMENTAL_PROGRESSION/01_early_phases.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases.md). Commit: `2e8c1a4` (Phase 14 close).
* `outputs/logs/phase09_bird_evidence_audit.md` — audit of the v9 evidence-block prompt design, with 60 sampled items showing the evidence-misuse failure category dropping from 39 % to 21 %. Underpins [07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md](../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md) §2.

### 2.2 Spider 2 entry and early plateaus (Phases 15–17)

* `outputs/REPORT_SPIDER2_V15_FIRST_BQ.md` — first Spider2-Lite-BQ submission, 0 % baseline; documents the schema-pack v1 design and its failure mode (BM25 over global index). Underpins [06_EXPERIMENTAL_PROGRESSION/01_early_phases.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases.md) §3.
* `outputs/REPORT_SPIDER2_V17_MODEL_SWAP.md` — Phase 17 four-models × two-lanes model-swap pilot. The "family > scale" finding (Qwen-Coder family outperforms larger non-Coder models at our pipeline) is from this report. Underpins [04_ARCHITECTURE/02_model_choice.md](../04_ARCHITECTURE/02_model_choice.md) §3. Commit: `9f1b8c1`.

### 2.3 Schema-first pivot and repair sprint (Phases 18–19)

* `outputs/REPORT_SPIDER2_V18_SCHEMA_FIRST.md` — Phase 18 schema-first pivot, BQ Lite from 10 % to 30 %. Documents the closed-set planner v18 design. Underpins [08_CUSTOM_TOOLS/01_schema_pack_builder_v18.md](../08_CUSTOM_TOOLS/01_schema_pack_builder_v18.md). Commit: `c12a334`.
* `outputs/REPORT_SPIDER2_V19_REPAIR_SPRINT.md` — Phase 19 seven-patch repair sprint, lifting Lite-BQ to 30 % schema_valid + 30 % dry_run_ok. Documents the validator-feedback patches. Underpins [06_EXPERIMENTAL_PROGRESSION/01_early_phases.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases.md) §5. Commit: `5d2ff79`.
* `outputs/logs/phase19_pack_thinness_audit.md` — pack-thinness audit on Lite-BQ that predicted +20 pp for STAGE A3; the observed +4 pp gap drives the Phase 22 architectural critique. Underpins [09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md](../09_RESULTS_ANALYSIS/01_classical_benchmarks_spider1_bird.md) and the BQ section of [07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md](../07_METRICS_AND_RESULTS/04_error_taxonomy_evolution.md).

### 2.4 STAGE A1/A2/A3 convergence (Phases 20–22)

* `outputs/REPORT_SPIDER2_V20_STAGE_A1.md` — STAGE A1 identifier canonicaliser; plan_validation_ok 42 → 54 %, chosen_schema_valid unchanged. Underpins [06_EXPERIMENTAL_PROGRESSION/01_early_phases.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases.md) §6. Commit: `7a39e21`.
* `outputs/REPORT_SPIDER2_V21_STAGE_A1_CONVERGE.md` — Phase 21 metric-label fix + UNNEST alias trust; 4-session pilot 50 stable in sv 50–52 % / exec 42–46 %. Commit: `b9c6f0d`.
* `outputs/REPORT_SPIDER2_V22.md` — Phase 22 STAGE A1+A2+A3 pack including all_columns + join_hints + Family C; sv 50 → 54 %. The pack-thinness audit prediction-vs-observed gap is logged here. Underpins [06_EXPERIMENTAL_PROGRESSION/01_early_phases.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases.md) §7 and the Lite-BQ plateau analysis. Commit: `e3140a7`.

### 2.5 FULL diagnostic and orchestration fix (Phases 23–24)

* `outputs/REPORT_SPIDER2_V23_FULL_DIAGNOSTIC.md` — Phase 23 concurrent BG-inference attempt, OOM on A100 80 GB, BQ FULL 14/205 partial, both Snow CANCELLED, DBT BLOCKED. Documents the GPU-contention diagnosis. Underpins [06_EXPERIMENTAL_PROGRESSION/01_early_phases.md](../06_EXPERIMENTAL_PROGRESSION/01_early_phases.md) §8 and the orchestration-fix narrative. Commit: `5f6a39b`.
* `outputs/REPORT_SPIDER2_V24_ORCH_FIX.md` — Phase 24 GPU lock + sequential runner; pilot 50 v24 reproduced v22 numbers exactly (sv 54 %, exec 44 %). Documents the orchestration recovery. Underpins [04_ARCHITECTURE/09_orchestration.md](../04_ARCHITECTURE/09_orchestration.md). Commit: `928a598`.
* `outputs/logs/phase23_orchestration_oom_diagnostic.md` — root-cause analysis of the Phase 23 OOM, with the GPU memory profile showing 84.6 GB peak vs 80 GB available. Underpins [08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md) §2.

### 2.6 DBT submission and stable rerun (Phases 25–26)

* `outputs/REPORT_SPIDER2_V25_DBT_STABLE.md` — Phase 25 v24 stable DBT rerun, 13.2 % task success on 68 tasks with the breakdown (9 success / 5 dbt_test_failed / 17 ran_ok_but_score_zero / 37 dbt_run_failed). The authoritative DBT publication figure. Underpins [09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md](../09_RESULTS_ANALYSIS/04_spider2_dbt_analysis.md). Commit: `f81c2e0`.
* `outputs/REPORT_SPIDER2_V26_RESEARCH_HANDOFF.md` — Phase 26 cross-DB-drift diagnostic that identified the global-BM25 root cause and motivated the F1 grounding stack. Documents the gap analysis that motivates Phase 27 F1. Underpins [06_EXPERIMENTAL_PROGRESSION/02_phase26_research_handoff.md](../06_EXPERIMENTAL_PROGRESSION/02_phase26_research_handoff.md). Commit: `4c91a5b`.

### 2.7 Phase 27 F1 grounding

* `outputs/REPORT_SPIDER2_V27_F1_GROUNDING.md` — the canonical Phase 27 report. Documents the per-task BM25 partition, SQLGlot AST guard, PK/FK injection, retrieval scaling, validator relaxation, and SELECT-alias protection. Pilot 10 result: 8/10 schema_valid (up from 0/10), 1/10 exec_ok. Underpins [06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md](../06_EXPERIMENTAL_PROGRESSION/03_phase27_f1_grounding.md) and the entire Snow-lane breakthrough narrative. Commit: `7b420b2`.
* `outputs/logs/phase27_bm25_partition_design.md` — design memo for the per-task BM25 partition keyed by `c.db.upper()`. Includes the failure-case enumeration that motivated the design. Underpins [08_CUSTOM_TOOLS/03_schema_linking_v18.md](../08_CUSTOM_TOOLS/03_schema_linking_v18.md) §4.
* `outputs/logs/phase27_pk_fk_injection_design.md` — design memo for the heuristic PK/FK injection rules. Underpins [08_CUSTOM_TOOLS/04_candidate_selector_v18.md](../08_CUSTOM_TOOLS/04_candidate_selector_v18.md) §3.

### 2.8 Phase 28 F2a regression and revert

* `outputs/REPORT_SPIDER2_V28_F2A_REGRESSION.md` — Phase 28 F2a + F4 + F4c initial deployment; pilot 10 went from 1/10 to 0/10 exec_ok, falsifying the F2a hypothesis. Underpins [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md) §3. Commit: `8acb0e5`.
* `outputs/logs/phase28_catalog_probe_patents.md` — the catalog probe that revealed the PATENTS schema's columns are stored lowercase, falsifying the F2a auto-uppercase hypothesis. The methodological centrepiece of the dossier's Claim 3 (catalog probing before dialect heuristic deployment). Underpins [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md) §4.
* `outputs/REPORT_SPIDER2_V28_REVERT_A.md` — Phase 28 closure report. F2a reverted, F4 + F4c retained; pilot 10 exec 0 → 4/10. The clean-baseline pilot result. Underpins [06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md](../06_EXPERIMENTAL_PROGRESSION/04_phase28_f2a_regression_and_revert.md) §5. Commit: `ad5493b`.
* `outputs/logs/phase28_f4_wrap_design.md` — design memo for the F4 NUMBER/VARIANT date-cast wrapper. Includes the SQLGlot TimestampTrunc-vs-DateTrunc discovery. Underpins [08_CUSTOM_TOOLS/06_snow_dialect_fixer_v28.md](../08_CUSTOM_TOOLS/06_snow_dialect_fixer_v28.md) §2.

### 2.9 Phase 28 FULL run

* `outputs/REPORT_SPIDER2_V28_FULL_BASELINE.md` — **Snow FULL closed (n=547, 23.76 % EXPLAIN-pass (\*)); Lite-Snow FULL partial (n=40 of 207, kernel-death event)**. Headline numbers, per-DB breakdown, and failure-class distribution are documented in [06_EXPERIMENTAL_PROGRESSION/05_phase28_full_baseline.md](../06_EXPERIMENTAL_PROGRESSION/05_phase28_full_baseline.md) (populated this dossier compilation). Lite-Snow full closure and row-match audit deferred to Phase 28b post-defence.

### 2.10 Cross-phase audit and lesson logs

* `outputs/logs/final_scientific_findings.md` — running list of validated scientific claims, one per claim, with the commit and report that establishes it. Underpins the Cross-Cutting Observations section of [07_METRICS_AND_RESULTS/02_progression_table_full.md](../07_METRICS_AND_RESULTS/02_progression_table_full.md).
* `outputs/logs/final_negative_result_analysis.md` — running list of falsified hypotheses (F2a being the headline). Underpins [06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md](../06_EXPERIMENTAL_PROGRESSION/06_lessons_learned.md).
* `outputs/REPORT.md` — top-level dossier index, updated at the close of each phase. Currently reflects Phase 28-revert-A; will be updated post-FULL.

## 3. Result-set artefacts

Every published number traces to a `metrics.json` plus `predictions.jsonl` plus `traces.jsonl` triple in one of the per-engine result directories. The canonical paths for each publication number:

* **Spider 1.0 94.0 % EX** — `outputs/spider1/v22_stable/metrics.json` + `predictions.jsonl` + `traces.jsonl`. The dev-split run at commit `e3140a7`.
* **BIRD 87.9 % EX FULL / 90.4 % mini-dev** — `outputs/bird/v22_stable/full/metrics.json` and `outputs/bird/v22_stable/mini_dev/metrics.json` plus accompanying JSONLs.
* **Spider2-Lite-BQ 30 % exec_ok plateau** — `outputs/bigquery/v24_stable_pilot50/metrics.json` plus JSONLs.
* **Spider2-DBT 13.2 %** — `outputs/dbt/v24_stable/metrics.json` plus the per-task `dbt_run_log/` and `dbt_test_log/` directories.
* **Spider2-Lite-Snow pilot 10 4/10 exec_ok** — `outputs/snowflake/phase28_revert_a_pilot10_lite/metrics.json` + JSONLs.
* **Spider2-Snow pilot 10 4/10 exec_ok** — `outputs/snowflake/phase28_revert_a_pilot10_snow/metrics.json` + JSONLs.
* **Spider2-Snow FULL 547 (23.76 % EXPLAIN-pass (\*), 130/547)** — canonical artefacts at `outputs/spider2_snow/runs/snow_full_v28_revert_a/`: `metrics.csv`, `predictions.jsonl`, `traces.jsonl`, `error_taxonomy.csv`, `progress.json`, `_DONE` (with full headline JSON payload).
* **Spider2-Lite-Snow FULL 207 (partial n=40)** — partial run at `outputs/spider2_lite/runs/lite_snow_full_v28_revert_a/` (snapshot prior to kernel-death; full closure deferred to Phase 28b).

## 4. Reproducibility notes

The reports indexed above are committed verbatim to the repository at the commits listed; they are not regenerated. Re-running a phase will produce a *new* directory (e.g. `outputs/snowflake/phase28_replay_2026_05_*`) rather than overwriting the canonical one. The publication numbers cite the canonical directories and the canonical commits; any future re-runs are treated as independent observations of the same hypothesis, not as updates to the publication figure.

A small number of `metrics.json` files in the per-engine directories were regenerated post-hoc when the metric-definition file changed (e.g. when we added `wrapped_n` as a counter in Phase 28). These regenerations are noted in the corresponding directory's `_REGENERATED.md` and do not change the underlying `predictions.jsonl` content — they only re-aggregate over the same predictions.

The Phase 28 FULL placeholder will be populated at closure with the same conventions: a frozen `outputs/snowflake/phase28_full_s1/_DONE` file marking the canonical run, plus the `REPORT_SPIDER2_V28_FULL_BASELINE.md` written against the metrics in that directory.
