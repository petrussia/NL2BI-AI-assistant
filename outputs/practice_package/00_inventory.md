# Practice Package Inventory

Single source of truth for what artefact goes where in the practice writeup.
The same data lives machine-readable in `00_inventory.csv` (one row per file).

Convention: paths are relative to `D:\HSE\Диплом\NL2BI-AI-assistant\`.

## 1. Metrics (5 files — all key, all in body + appendix)

| Path | Use |
|---|---|
| `outputs/metrics/b0_spider_smoke10_metrics.csv` | EX, executable, n. Cite. |
| `outputs/metrics/b1_spider_smoke10_metrics.csv` | + avg_reduction_ratio. Cite. |
| `outputs/metrics/b0_spider_smoke25_metrics.csv` | EX, executable, n. Cite. |
| `outputs/metrics/b1_spider_smoke25_metrics.csv` | + avg_reduction_ratio. Cite. |
| `outputs/metrics/b2_spider_smoke10_metrics.csv` | + plan_valid_count, plan_parse_failures. Cite. |

## 2. Plots (4 PNGs — all candidates for figures)

| Path | Caption draft |
|---|---|
| `outputs/plots/b0_vs_b1_smoke10_bar.png` | "EX of B0 vs B1 on Spider smoke10 (n=10)." |
| `outputs/plots/b0_vs_b1_smoke25_bar.png` | "EX of B0 vs B1 on Spider smoke25 (n=25)." |
| `outputs/plots/baseline_progression_smoke10_smoke25.png` | "Aggregate EX progression of B0 and B1 across smoke10 and smoke25." |
| `outputs/plots/b0_b1_b2_smoke10_bar.png` | "Three-way EX of B0 vs B1 vs B2 on Spider smoke10." |

## 3. Comparison tables (8 files — main results)

| Path | Use |
|---|---|
| `outputs/tables/b0_vs_b1_smoke10_comparison.csv` + `.md` | smoke10 head-to-head |
| `outputs/tables/b0_vs_b1_smoke25_comparison.csv` + `.md` | smoke25 head-to-head |
| `outputs/tables/b0_b1_b2_smoke10_comparison.csv` + `.md` | three-way smoke10 (main results table) |
| `outputs/tables/baseline_progression_smoke10_smoke25.csv` + `.md` | aggregate, with delta and conclusion sentence |

## 4. Error analysis (10 files — pick selectively)

Must include in body:
- `outputs/tables/error_taxonomy_smoke25.md` — bucket definitions + per-cell breakdown.
- `outputs/tables/b2_spider_smoke10_error_cases.md` — short, only 3 cases, fits in one half-page.
- `outputs/tables/b2_plan_examples_smoke10.md` — five planner traces (question → plan → SQL).
- `outputs/tables/b0_b1_b2_smoke10_case_diff.md` — at least one case demonstrating B2 regression.

Appendix only:
- `outputs/tables/b0_vs_b1_case_diff.md`, `b0_vs_b1_smoke25_case_diff.md` — paired diffs (mostly tie cases on this data, low signal).
- `outputs/tables/b1_schema_linking_examples.md` and `b1_schema_linking_smoke25_examples.md` — per-question linking decisions.
- `outputs/tables/b{0,1,2}_spider_smoke{10,25}_examples.md` — first 5 predictions; supporting only.
- `outputs/tables/b{0,1}_spider_smoke25_error_cases.md` — 1 case each, both same idx 16.
- `outputs/tables/b0_b1_failure_buckets.csv` — bucket counts in tabular form.
- `outputs/tables/b{0,1,2}_spider_smoke*_summary.csv` — key/value summaries.

Skip entirely (empty / superseded):
- `outputs/tables/b0_spider_smoke10_error_cases.md` — empty (no errors on smoke10).
- `outputs/tables/b1_spider_smoke10_error_cases.md` — empty.

## 5. Raw predictions (5 jsonl — appendix references only)

| Path | n rows | extra fields |
|---|---|---|
| `outputs/predictions/b0_spider_smoke10_predictions.jsonl` | 10 | — |
| `outputs/predictions/b1_spider_smoke10_predictions.jsonl` | 10 | `selected_tables`, `schema_reduction_ratio`, `fallback_used` |
| `outputs/predictions/b0_spider_smoke25_predictions.jsonl` | 25 | — |
| `outputs/predictions/b1_spider_smoke25_predictions.jsonl` | 25 | (B1 fields) |
| `outputs/predictions/b2_spider_smoke10_predictions.jsonl` | 10 | + `plan_raw`, `plan_parsed`, `plan_valid`, `plan_error` |

Mention as "Прил. 1: Полные предсказания моделей в формате JSONL", do not paste content.

## 6. Logs / audits (29 files — cherry-pick)

In body / methods:
- `outputs/logs/runtime_project_root_audit.md` — GPU + library versions.
- `outputs/logs/smoke25_subset_audit.md` — subset description.
- `outputs/logs/b1_schema_linking_audit.md`, `b1_schema_linking_smoke25_audit.md` — linker stats.
- `outputs/logs/b2_design_decision.md` — B2 minimal pipeline rationale + plan schema author note.
- `outputs/logs/next_step_after_b2.md` — quoted in conclusion.

Appendix:
- `outputs/logs/{b0,b1,b2}_spider_*_runlog.txt` — five runlogs, reproducibility evidence.
- `outputs/logs/{smoke25,b2_smoke10}_bg_task_log.txt` — two background-thread task logs.
- `outputs/logs/bridge_status_drive.md`, `artifact_recheck_drive.md`, `b2_preflight_drive.md`, `b0_blockers_audit.md`, `b0_physical_recheck.md`, `b0_loader_subsets_audit.md`, `b2_implementation_plan.md`, `b2_readiness_after_smoke25.md` — methodological evidence trail.

Skip:
- `outputs/logs/local_helper_script_audit.md`, `local_notebook_audit.md`, `b1_ready_checklist.md`, `next_step_readiness.md` — superseded by later docs (bridge tooling, B2 readiness).
- `outputs/logs/thesis_*.md` — for the diploma chapter, not the practice report.
- `outputs/logs/_bridge_write_test.txt` — debug only.

## 7. Practice docs already prepared (5 files — reuse text)

| Path | Use |
|---|---|
| `practice/practice_worklog_draft.md` | Source for "что было сделано" section. |
| `practice/practice_evidence_checklist.md` | Source for evidence list. |
| `practice/practice_tasks_mapping.md` | Source for task-to-evidence binding. |
| `practice/practice_figure_index.md` | Pre-built figure list. |
| `practice/practice_table_index.md` | Pre-built table list. |

## 8. Repo artefacts / appendices (4 files)

| Path | Use |
|---|---|
| `repo/docs/plan_schema.json` | B2 planner JSON schema. Full text in appendix; brief mention in methods. |
| `repo/src/evaluation/baselines.py` | B1 lexical schema linker. Code listing in appendix. |
| `repo/src/evaluation/baselines_b2.py` | B2 Plan→SQL module. Code listing in appendix. |
| `data/spider/SOURCE_AND_AUDIT.md` | Spider provenance and integrity audit. Methods + appendix. |

---

## Counts

- Metrics: 5
- Plots: 4
- Comparison tables: 8 (4 csv + 4 md)
- Error analysis: 18 (selective)
- Raw predictions: 5 jsonl
- Logs/audits: 29 (selective)
- Practice docs already prepared: 5
- Repo artefacts: 4

Total inventory: **78 files** classified. Use-in-report: **~25 files**. Use-in-appendix-only: **~35 files**. Skip: **~18 files**.
