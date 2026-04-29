# Practice Tasks Mapping

Updated 2026-04-25T17:55:21.925124+00:00.

| Task | Evidence on Drive | Status |
|---|---|---|
| Notebook + helper script audit | `outputs/logs/local_*_audit.md`, `tools/notebook_tooling_audit.md`, `tools/run_cell_changelog.md` | completed |
| Runtime + Drive audit | `outputs/logs/runtime_project_root_audit.md`, `outputs/logs/bridge_status_drive.md` | completed |
| Spider asset acquisition + integrity | `outputs/logs/b0_blockers_audit.md`, `data/spider/SOURCE_AND_AUDIT.md` | completed |
| Loader + smoke subsets | `outputs/logs/b0_loader_subsets_audit.md`, `outputs/logs/smoke25_subset_audit.md` | completed |
| B0 baseline (smoke10, smoke25) | `outputs/predictions/b0_spider_*.jsonl`, `outputs/metrics/b0_spider_*.csv`, `outputs/tables/b0_spider_*_*.{csv,md}`, `outputs/logs/b0_spider_*_runlog.txt` | completed |
| B1 lexical schema linking impl | `repo/src/evaluation/baselines.py`, `outputs/tables/b1_schema_linking_*.md`, `outputs/logs/b1_schema_linking_*.md` | completed |
| B1 baseline (smoke10, smoke25) | `outputs/predictions/b1_spider_*.jsonl`, `outputs/metrics/b1_spider_*.csv`, `outputs/tables/b1_spider_*_*.{csv,md}`, `outputs/logs/b1_spider_*_runlog.txt` | completed |
| B0 vs B1 comparisons | `outputs/tables/b0_vs_b1_smoke{10,25}_*.{csv,md,png}`, `outputs/tables/b0_vs_b1_*case_diff.md` | completed |
| Aggregate progression | `outputs/tables/baseline_progression_smoke10_smoke25.{csv,md}`, `outputs/plots/baseline_progression_smoke10_smoke25.png` | completed |
| Error taxonomy | `outputs/tables/error_taxonomy_smoke25.md`, `outputs/tables/b0_b1_failure_buckets.csv` | completed |
| Bridge tooling | `tools/bridge_status.md`, `tools/exec_remote.py`, notebook cell `AGENT_BRIDGE_SETUP` (id `7f6bca53`) | completed |
| B2 plan schema + design | `repo/docs/plan_schema.json`, `outputs/logs/b2_design_decision.md` | completed |
| B2 module impl | `repo/src/evaluation/baselines_b2.py` (`make_plan_prompt`, `extract_json_block`, `parse_and_validate_plan`, `make_plan_to_sql_prompt`) | completed |
| B2 baseline (smoke10) | `outputs/predictions/b2_spider_smoke10_predictions.jsonl`, `outputs/metrics/b2_spider_smoke10_metrics.csv`, `outputs/tables/b2_spider_smoke10_*.{csv,md}`, `outputs/logs/b2_spider_smoke10_runlog.txt`, `outputs/tables/b2_plan_examples_smoke10.md` | completed |
| B0 vs B1 vs B2 three-way | `outputs/tables/b0_b1_b2_smoke10_comparison.{csv,md}`, `outputs/plots/b0_b1_b2_smoke10_bar.png`, `outputs/tables/b0_b1_b2_smoke10_case_diff.md` | completed |
| B2 on smoke25 | — | not started (next step) |
| Multi-DB subset | — | not started |
| B3 / B4 / fine-tuning | — | out of scope |
| Final practice + thesis writeups | — | deferred |
