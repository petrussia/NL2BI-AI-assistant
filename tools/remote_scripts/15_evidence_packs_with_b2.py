# Step 15: refresh practice + thesis evidence packs to include B2 smoke10.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PRACTICE = PROJECT_ROOT / 'practice'
PRACTICE.mkdir(parents=True, exist_ok=True)
LOGS = OUTPUTS / 'logs'
ts = dt.datetime.now(dt.timezone.utc).isoformat()


def load_csv_one(p):
    if not p.exists(): return None
    return list(csv.DictReader(p.open(encoding='utf-8')))[0]


b0_10 = load_csv_one(OUTPUTS / 'metrics' / 'b0_spider_smoke10_metrics.csv')
b1_10 = load_csv_one(OUTPUTS / 'metrics' / 'b1_spider_smoke10_metrics.csv')
b2_10 = load_csv_one(OUTPUTS / 'metrics' / 'b2_spider_smoke10_metrics.csv')
b0_25 = load_csv_one(OUTPUTS / 'metrics' / 'b0_spider_smoke25_metrics.csv')
b1_25 = load_csv_one(OUTPUTS / 'metrics' / 'b1_spider_smoke25_metrics.csv')


# ---------- practice ----------
worklog = f'''# Practice Worklog Draft

## Current State (updated {ts})

### B0 (full schema baseline)
- smoke10: EX={b0_10.get("ex") if b0_10 else "?"}, executable {b0_10.get("executable_count") if b0_10 else "?"}/{b0_10.get("n") if b0_10 else "?"}
- smoke25: EX={b0_25.get("ex") if b0_25 else "?"}, executable {b0_25.get("executable_count") if b0_25 else "?"}/{b0_25.get("n") if b0_25 else "?"}
- model: Qwen/Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes), greedy

### B1 (reduced schema via lexical schema linking)
- smoke10: EX={b1_10.get("ex") if b1_10 else "?"}, avg reduction {b1_10.get("avg_reduction_ratio") if b1_10 else "?"}
- smoke25: EX={b1_25.get("ex") if b1_25 else "?"}, avg reduction {b1_25.get("avg_reduction_ratio") if b1_25 else "?"}

### B2 (Plan->SQL minimal pipeline)
- smoke10: EX={b2_10.get("ex") if b2_10 else "?"}, executable {b2_10.get("executable_count") if b2_10 else "?"}/{b2_10.get("n") if b2_10 else "?"}, plan_valid {b2_10.get("plan_valid_count") if b2_10 else "?"}/{b2_10.get("n") if b2_10 else "?"}
- planner: JSON Plan validated against `repo/docs/plan_schema.json`
- module: `repo/src/evaluation/baselines_b2.py`
- design notes: `outputs/logs/b2_design_decision.md`

### Comparisons
- B0 vs B1 smoke10/smoke25 + aggregate progression smoke10→smoke25 (csv/md/png/case_diff)
- B0 vs B1 vs B2 smoke10 (csv/md/png/case_diff)

### Tooling
- Bridge tool primary path: `tools/exec_remote.py` over cloudflared tunnel from notebook cell `7f6bca53`
- Background-thread inference dispatcher pattern reused for both `04b_smoke25_b0_and_b1_bg.py` and `13_b2_smoke10_bg.py`

### Out of scope (intentionally not done)
- B2 on smoke25 (next candidate experiment)
- multi-DB sample (next-after-that)
- B3, B4, fine-tuning
- final practice and thesis chapters
'''
(PRACTICE / 'practice_worklog_draft.md').write_text(worklog, encoding='utf-8')

checklist = f'''# Practice Evidence Checklist

Updated {ts}.

## Smoke10
- [x] B0 predictions / metrics / summary / runlog / error_cases / examples
- [x] B1 predictions (incl. selected_tables, schema_reduction_ratio) / metrics / summary / runlog / error_cases / examples / linking examples + audit
- [x] B2 predictions (incl. plan_raw, plan_parsed, plan_valid, plan_error, selected_tables, schema_reduction_ratio) / metrics (incl. plan_valid_count, plan_parse_failures) / summary / runlog / error_cases / examples / plan_examples
- [x] B0 vs B1 comparison CSV/MD/plot/case_diff
- [x] B0 vs B1 vs B2 three-way comparison CSV/MD/plot/case_diff

## Smoke25
- [x] B0 predictions / metrics / summary / runlog / error_cases / examples
- [x] B1 predictions / metrics / summary / runlog / error_cases / examples / linking examples + audit
- [x] B0 vs B1 comparison CSV/MD/plot/case_diff
- [x] aggregate progression smoke10→smoke25 CSV/MD/plot

## Cross-cutting
- [x] error_taxonomy_smoke25.md, b0_b1_failure_buckets.csv
- [x] practice_figure_index.md, practice_table_index.md
- [x] B2 design decision (`outputs/logs/b2_design_decision.md`)
- [x] B2 readiness, B2 implementation plan
- [x] B2 preflight (`outputs/logs/b2_preflight_drive.md`)

## Out of scope
- [ ] B2 on smoke25
- [ ] multi-DB subset evaluation
- [ ] B3/B4
- [ ] fine-tuning
- [ ] final practice and thesis writeups
'''
(PRACTICE / 'practice_evidence_checklist.md').write_text(checklist, encoding='utf-8')

mapping = f'''# Practice Tasks Mapping

Updated {ts}.

| Task | Evidence on Drive | Status |
|---|---|---|
| Notebook + helper script audit | `outputs/logs/local_*_audit.md`, `tools/notebook_tooling_audit.md`, `tools/run_cell_changelog.md` | completed |
| Runtime + Drive audit | `outputs/logs/runtime_project_root_audit.md`, `outputs/logs/bridge_status_drive.md` | completed |
| Spider asset acquisition + integrity | `outputs/logs/b0_blockers_audit.md`, `data/spider/SOURCE_AND_AUDIT.md` | completed |
| Loader + smoke subsets | `outputs/logs/b0_loader_subsets_audit.md`, `outputs/logs/smoke25_subset_audit.md` | completed |
| B0 baseline (smoke10, smoke25) | `outputs/predictions/b0_spider_*.jsonl`, `outputs/metrics/b0_spider_*.csv`, `outputs/tables/b0_spider_*_*.{{csv,md}}`, `outputs/logs/b0_spider_*_runlog.txt` | completed |
| B1 lexical schema linking impl | `repo/src/evaluation/baselines.py`, `outputs/tables/b1_schema_linking_*.md`, `outputs/logs/b1_schema_linking_*.md` | completed |
| B1 baseline (smoke10, smoke25) | `outputs/predictions/b1_spider_*.jsonl`, `outputs/metrics/b1_spider_*.csv`, `outputs/tables/b1_spider_*_*.{{csv,md}}`, `outputs/logs/b1_spider_*_runlog.txt` | completed |
| B0 vs B1 comparisons | `outputs/tables/b0_vs_b1_smoke{{10,25}}_*.{{csv,md,png}}`, `outputs/tables/b0_vs_b1_*case_diff.md` | completed |
| Aggregate progression | `outputs/tables/baseline_progression_smoke10_smoke25.{{csv,md}}`, `outputs/plots/baseline_progression_smoke10_smoke25.png` | completed |
| Error taxonomy | `outputs/tables/error_taxonomy_smoke25.md`, `outputs/tables/b0_b1_failure_buckets.csv` | completed |
| Bridge tooling | `tools/bridge_status.md`, `tools/exec_remote.py`, notebook cell `AGENT_BRIDGE_SETUP` (id `7f6bca53`) | completed |
| B2 plan schema + design | `repo/docs/plan_schema.json`, `outputs/logs/b2_design_decision.md` | completed |
| B2 module impl | `repo/src/evaluation/baselines_b2.py` (`make_plan_prompt`, `extract_json_block`, `parse_and_validate_plan`, `make_plan_to_sql_prompt`) | completed |
| B2 baseline (smoke10) | `outputs/predictions/b2_spider_smoke10_predictions.jsonl`, `outputs/metrics/b2_spider_smoke10_metrics.csv`, `outputs/tables/b2_spider_smoke10_*.{{csv,md}}`, `outputs/logs/b2_spider_smoke10_runlog.txt`, `outputs/tables/b2_plan_examples_smoke10.md` | completed |
| B0 vs B1 vs B2 three-way | `outputs/tables/b0_b1_b2_smoke10_comparison.{{csv,md}}`, `outputs/plots/b0_b1_b2_smoke10_bar.png`, `outputs/tables/b0_b1_b2_smoke10_case_diff.md` | completed |
| B2 on smoke25 | — | not started (next step) |
| Multi-DB subset | — | not started |
| B3 / B4 / fine-tuning | — | out of scope |
| Final practice + thesis writeups | — | deferred |
'''
(PRACTICE / 'practice_tasks_mapping.md').write_text(mapping, encoding='utf-8')

# Figure & table indices
fig_index = f'''# Practice Figure Index

Updated {ts}.

| Path | Caption / role | Use |
|---|---|---|
| `outputs/plots/b0_vs_b1_smoke10_bar.png` | EX comparison B0 vs B1 on smoke10 | smoke10 results |
| `outputs/plots/b0_vs_b1_smoke25_bar.png` | EX comparison B0 vs B1 on smoke25 | smoke25 results |
| `outputs/plots/baseline_progression_smoke10_smoke25.png` | Aggregate B0/B1 progression smoke10→smoke25 | progression analysis |
| `outputs/plots/b0_b1_b2_smoke10_bar.png` | Three-way EX B0 vs B1 vs B2 on smoke10 | B2 introduction |

All plots are matplotlib bar charts at 140 DPI.
'''
(PRACTICE / 'practice_figure_index.md').write_text(fig_index, encoding='utf-8')

tbl_index = f'''# Practice Table Index

Updated {ts}.

## Numeric tables (CSV)
- `outputs/metrics/{{b0,b1,b2}}_spider_smoke10_metrics.csv` (B2 has plan_valid_count, plan_parse_failures)
- `outputs/metrics/{{b0,b1}}_spider_smoke25_metrics.csv`
- `outputs/tables/{{b0,b1,b2}}_spider_smoke10_summary.csv`
- `outputs/tables/{{b0,b1}}_spider_smoke25_summary.csv`
- `outputs/tables/b0_vs_b1_smoke{{10,25}}_comparison.csv`
- `outputs/tables/b0_b1_b2_smoke10_comparison.csv`
- `outputs/tables/baseline_progression_smoke10_smoke25.csv`
- `outputs/tables/b0_b1_failure_buckets.csv`

## Narrative tables (Markdown)
- `outputs/tables/{{b0,b1,b2}}_spider_smoke{{10,25}}_examples.md` and `_error_cases.md`
- `outputs/tables/b1_schema_linking{{,_smoke25}}_examples.md`
- `outputs/tables/b0_vs_b1_smoke{{10,25}}_comparison.md` and `_case_diff.md`
- `outputs/tables/b0_b1_b2_smoke10_comparison.md` and `_case_diff.md`
- `outputs/tables/b2_plan_examples_smoke10.md`
- `outputs/tables/baseline_progression_smoke10_smoke25.md`
- `outputs/tables/error_taxonomy_smoke25.md`
'''
(PRACTICE / 'practice_table_index.md').write_text(tbl_index, encoding='utf-8')


# ---------- thesis ----------
thesis_inv = f'''# Thesis Experiment Inventory

Updated {ts}.

## Baselines implemented
- **B0** — full-schema NL→SQL prompt, Qwen/Qwen2.5-Coder-7B-Instruct, 4-bit `nf4` bitsandbytes, greedy, max_new_tokens=192. SQL extracted by regex; executed via SQLite with 8 s timeout.
- **B1** — same model + decoding, but the schema in the prompt is reduced via *lexical schema linking* (token overlap, table-name x2, column-name x1, English stopwords removed, `min_score=0.5`). Tables with no signal trigger a fallback to the full schema.
- **B2** — same model + decoding, two-stage *Plan→SQL* pipeline. Stage A: planner emits a strict JSON Plan validated against `repo/docs/plan_schema.json` (intent, tables, operations required; columns/filters/aggregations/group_by/order_by/limit/joins optional, `additionalProperties: false`). Stage B: plan + reduced schema → SQL prompt → SQL → execute. Invalid plan is recorded as `error_type=plan_invalid`; no repair / retry yet.

## Subsets evaluated
- `smoke_10` (n=10, all `concert_singer`): B0 + B1 + B2 done.
- `smoke_25` (n=25, all `concert_singer`, smoke10 ⊂ smoke25): B0 + B1 done; B2 not yet.
- `smoke_50` exists on Drive; not evaluated.
- Spider dev (n=1034) not evaluated.

## Metrics
- **EX** — execution-match against gold SQL on SQLite.
- **executable_count** — predicted SQL parses and runs.
- **plan_valid_count (B2)** — JSON plan parsed and validated against `plan_schema.json`.
- **plan_parse_failures (B2)** — JSON could not even be parsed.
- **avg_reduction_ratio (B1, B2)** — mean fraction of full schema kept by the lexical linker.

## Comparisons produced
- B0 vs B1 on smoke10 and smoke25 (CSV/MD/PNG/case_diff).
- Aggregate progression smoke10→smoke25 (CSV/MD/PNG).
- Error taxonomy on smoke25 (8 buckets, per-cell breakdown).
- B0 vs B1 vs B2 on smoke10 (CSV/MD/PNG/case_diff).

## Reproducibility evidence
- Model + GPU + library versions: `outputs/logs/runtime_project_root_audit.md`.
- Spider source provenance: `data/spider/SOURCE_AND_AUDIT.md`.
- Subset audits: `outputs/logs/b0_loader_subsets_audit.md`, `outputs/logs/smoke25_subset_audit.md`.
- Per-run logs: `outputs/logs/{{b0,b1,b2}}_spider_*_runlog.txt`.
- Bridge tooling state: `outputs/logs/bridge_status_drive.md`, `outputs/logs/artifact_recheck_drive.md`.
- B2 design + plan schema authorship: `outputs/logs/b2_design_decision.md`, `outputs/logs/b2_preflight_drive.md`.
- Tooling audit: `tools/notebook_tooling_audit.md`, `tools/run_cell_changelog.md`, `tools/tool_manifest.md`.

## Limitations to disclose
- Single-DB subsets bound the schema-linking benefit. Multi-DB sample is the next critical experiment.
- 4-bit quantisation; numerical sensitivity not measured.
- Single greedy decoding (no sampling, no self-consistency, no multi-candidate selection).
- B2 has no repair / retry loop; invalid plan ⇒ no SQL ⇒ counts as wrong.
- EX is execution-only; logical-form / partial-credit metrics not computed.
'''
(LOGS / 'thesis_experiment_inventory.md').write_text(thesis_inv, encoding='utf-8')

thesis_fig = f'''# Thesis Figure Index

Updated {ts}.

| Suggested label | Path | Caption draft |
|---|---|---|
| Fig. baseline_smoke10 | `outputs/plots/b0_vs_b1_smoke10_bar.png` | EX of B0 vs B1 on Spider smoke10 (n=10), Qwen2.5-Coder-7B-Instruct, greedy. |
| Fig. baseline_smoke25 | `outputs/plots/b0_vs_b1_smoke25_bar.png` | EX of B0 vs B1 on Spider smoke25 (n=25). |
| Fig. progression | `outputs/plots/baseline_progression_smoke10_smoke25.png` | Aggregate EX progression of B0 and B1 across smoke10 and smoke25. |
| Fig. b2_three_way | `outputs/plots/b0_b1_b2_smoke10_bar.png` | Three-way EX of B0 vs B1 vs B2 on Spider smoke10. |

All figures rendered at 140 DPI from the corresponding `outputs/metrics/*.csv` files.
'''
(LOGS / 'thesis_figure_index.md').write_text(thesis_fig, encoding='utf-8')

thesis_tbl = f'''# Thesis Table Index

Updated {ts}.

| Suggested label | Path | Notes |
|---|---|---|
| Tbl. metrics_summary | `outputs/tables/baseline_progression_smoke10_smoke25.csv` | Side-by-side B0/B1 across smoke10 and smoke25. Camera-ready: rename columns. |
| Tbl. smoke10_compare | `outputs/tables/b0_vs_b1_smoke10_comparison.csv` | B0 vs B1 head-to-head on smoke10. |
| Tbl. smoke25_compare | `outputs/tables/b0_vs_b1_smoke25_comparison.csv` | Same on smoke25. |
| Tbl. three_way_smoke10 | `outputs/tables/b0_b1_b2_smoke10_comparison.csv` | B0 vs B1 vs B2 with plan_valid_count column. |
| Tbl. failure_buckets | `outputs/tables/b0_b1_failure_buckets.csv` | Counts per error bucket on smoke25. |
| Tbl. linking_examples_smoke10 | `outputs/tables/b1_schema_linking_examples.md` | Per-question linking on smoke10. |
| Tbl. linking_examples_smoke25 | `outputs/tables/b1_schema_linking_smoke25_examples.md` | Per-question linking on smoke25. |
| Tbl. plan_examples_smoke10 | `outputs/tables/b2_plan_examples_smoke10.md` | First 5 question→plan→SQL traces for B2. |
| Tbl. case_diff_smoke25 | `outputs/tables/b0_vs_b1_smoke25_case_diff.md` | ≥5 paired cases. |
| Tbl. case_diff_three_way | `outputs/tables/b0_b1_b2_smoke10_case_diff.md` | ≥5 cases with B0/B1/B2 outcomes side by side. |
'''
(LOGS / 'thesis_table_index.md').write_text(thesis_tbl, encoding='utf-8')

thesis_methods = f'''# Thesis Methods Notes

Updated {ts}. Reusable phrasing for the experiments chapter; not the chapter itself.

## Setup paragraph
Spider dev split was loaded from the official YALE bundle. The first 10 and 25 examples define `smoke_10` and `smoke_25`; both fall in `concert_singer` (4 tables). All inference ran on a single NVIDIA L4 GPU in Google Colab using `Qwen/Qwen2.5-Coder-7B-Instruct` quantised to 4-bit `nf4` via `bitsandbytes`, greedy decoding (`do_sample=False`), `max_new_tokens=192` for SQL and 256 for plans. Generated SQL was extracted with a regex stripping markdown fences, executed via SQLite with an 8-second timeout (`func_timeout`), and compared to gold by row-multiset equality.

## Baselines paragraph
**B0** is a single-shot full-schema NL→SQL prompt. **B1** uses the same scaffold but replaces the schema block with a reduced one chosen by lexical schema linking (token overlap, table-name x2, column-name x1, English stopwords removed, `min_score=0.5`); tables with no signal trigger a full-schema fallback. **B2** is a two-stage Plan→SQL pipeline: a planner emits a JSON Plan validated against a strict schema with seven `intent` enum values and `additionalProperties: false`; the validated plan is then included in a second prompt that emits SQL. Invalid plans are recorded as `error_type=plan_invalid` and skip SQL generation.

## Results-shape paragraph
On smoke10, B0=B1={(b0_10.get("ex") if b0_10 else "?")} and B2={(b2_10.get("ex") if b2_10 else "?")}; B2 plan_valid={(b2_10.get("plan_valid_count") if b2_10 else "?")}/{(b2_10.get("n") if b2_10 else "?")}. On smoke25, B0=B1={(b0_25.get("ex") if b0_25 else "?")}; B2 not yet evaluated. Both subsets being from the same DB bounds the schema-linking benefit; B2 introduces planner overhead but adds an explicit verifiable artefact (the JSON Plan).

## Limitations paragraph
The schema-linking signal is bounded on `concert_singer` alone — irrelevant tables are at most 3 of 4. Stronger conclusions require a multi-DB subset where the linker can rule out *databases*, not just tables. EX is execution-equivalence only; logical equivalence and partial-credit metrics are not computed. The model is loaded in 4-bit; numerical sensitivity to the quantisation scheme is not measured. B2 has no repair loop, no multi-candidate selection, and no domain-doc retrieval — these belong to B2.5+ and B3+. No fine-tuning is performed.

## Tooling paragraph (for the methods appendix)
Inference cells are dispatched via a Cloudflare-tunnelled Flask server inside the Colab kernel (notebook cell `AGENT_BRIDGE_SETUP`, id `7f6bca53`). The local agent talks to the kernel directly over HTTPS; this avoids the focus-race failure of SendKeys-based notebook drivers when the agent's terminal output renders in the same VS Code window as the notebook. Predictions are saved incrementally so a Cloudflare HTTP timeout (~100 s) never loses data; the background thread continues writing to Drive after the request returns. The `13_b2_smoke10_bg.py` script reuses this pattern verbatim from `04b_smoke25_b0_and_b1_bg.py`.
'''
(LOGS / 'thesis_methods_notes.md').write_text(thesis_methods, encoding='utf-8')

print('practice files:', sorted(p.name for p in PRACTICE.iterdir()))
print('thesis files:', sorted(p.name for p in LOGS.iterdir() if p.name.startswith('thesis_')))
print('STATUS=DONE')
