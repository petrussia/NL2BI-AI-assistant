# Step 6: Practice + thesis evidence packs. Generated from metrics on Drive.
# Doesn't write a final report — these are inventory documents for what's
# ready to use in the eventual practice/thesis writeups.

import csv
import datetime as dt
import json
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PRACTICE = PROJECT_ROOT / 'practice'
PRACTICE.mkdir(parents=True, exist_ok=True)
ts = dt.datetime.now(dt.timezone.utc).isoformat()


def load_csv_one(p):
    if not p.exists(): return None
    return list(csv.DictReader(p.open(encoding='utf-8')))[0]


b0_10 = load_csv_one(OUTPUTS / 'metrics' / 'b0_spider_smoke10_metrics.csv')
b1_10 = load_csv_one(OUTPUTS / 'metrics' / 'b1_spider_smoke10_metrics.csv')
b0_25 = load_csv_one(OUTPUTS / 'metrics' / 'b0_spider_smoke25_metrics.csv')
b1_25 = load_csv_one(OUTPUTS / 'metrics' / 'b1_spider_smoke25_metrics.csv')


def fnum(d, k):
    if not d or d.get(k) in (None, ''): return None
    try: return float(d[k])
    except Exception: return d[k]


# ============= practice/practice_worklog_draft.md =============
worklog = f'''# Practice Worklog Draft

## Current State (updated {ts})

### B0 (full schema baseline)
- Status: completed on smoke10 and smoke25
- Subset smoke10: EX = {b0_10.get('ex') if b0_10 else 'n/a'}, executable {b0_10.get('executable_count') if b0_10 else 'n/a'}/{b0_10.get('n') if b0_10 else 'n/a'}
- Subset smoke25: EX = {b0_25.get('ex') if b0_25 else 'n/a'}, executable {b0_25.get('executable_count') if b0_25 else 'n/a'}/{b0_25.get('n') if b0_25 else 'n/a'}
- Model: Qwen/Qwen2.5-Coder-7B-Instruct (4-bit nf4 bitsandbytes), greedy decode
- Predictions: `outputs/predictions/b0_spider_{{smoke10,smoke25}}_predictions.jsonl`
- Metrics:     `outputs/metrics/b0_spider_{{smoke10,smoke25}}_metrics.csv`

### B1 (reduced schema via lexical schema linking)
- Status: completed on smoke10 and smoke25
- Schema strategy: lexical token overlap, table_name x2, column_name x1, min_score=0.5, stopwords removed
- Subset smoke10: EX = {b1_10.get('ex') if b1_10 else 'n/a'}, avg reduction = {b1_10.get('avg_reduction_ratio') if b1_10 else 'n/a'}
- Subset smoke25: EX = {b1_25.get('ex') if b1_25 else 'n/a'}, avg reduction = {b1_25.get('avg_reduction_ratio') if b1_25 else 'n/a'}
- Predictions: `outputs/predictions/b1_spider_{{smoke10,smoke25}}_predictions.jsonl` (with selected_tables, schema_reduction_ratio per row)
- Metrics:     `outputs/metrics/b1_spider_{{smoke10,smoke25}}_metrics.csv`
- Linking artefacts: `outputs/tables/b1_schema_linking_{{,smoke25_}}examples.md`, `outputs/logs/b1_schema_linking_{{,smoke25_}}audit.md`

### Comparisons
- smoke10 B0 vs B1: `outputs/tables/b0_vs_b1_smoke10_comparison.{{csv,md}}`, `outputs/plots/b0_vs_b1_smoke10_bar.png`, case_diff in tables/
- smoke25 B0 vs B1: `outputs/tables/b0_vs_b1_smoke25_comparison.{{csv,md}}`, `outputs/plots/b0_vs_b1_smoke25_bar.png`, case_diff in tables/
- Aggregate progression: `outputs/tables/baseline_progression_smoke10_smoke25.{{csv,md}}`, `outputs/plots/baseline_progression_smoke10_smoke25.png`

### Error analysis
- Bucketed: `outputs/tables/error_taxonomy_smoke25.md`
- Counts: `outputs/tables/b0_b1_failure_buckets.csv`

### Tooling for the loop
- Notebook: `notebooks/example.ipynb`
- Helper (legacy SendKeys, fragile in agent context): `scripts/run_colab_notebook.ps1`
- Bridge (Flask in Colab + cloudflared, primary mechanism): cell `7f6bca53` `AGENT_BRIDGE_SETUP`
- Local client: `tools/exec_remote.py` (--code, --code-file, --ls, --download, --health)
- Recheck/snapshot: `tools/notebook_status.py`, `tools/run_cell.py` (fallback)
- Manifests: `tools/tool_manifest.md`, `tools/tooling_readme.md`, `tools/notebook_tooling_audit.md`

### Out of scope for this iteration
- B2 (Plan->SQL with retrieval, validation, repair, exec-guided selection)
- Fine-tuning
- Multi-DB subsets beyond `concert_singer`
- Final practice and thesis chapters (evidence is being collected, writeup deferred)
'''
(PRACTICE / 'practice_worklog_draft.md').write_text(worklog, encoding='utf-8')

# ============= practice/practice_evidence_checklist.md =============
checklist = f'''# Practice Evidence Checklist

Updated {ts}.

## Smoke10
- [x] B0 predictions, metrics, summary, runlog, error_cases, examples
- [x] B1 predictions (incl. selected_tables, schema_reduction_ratio), metrics, summary, runlog, error_cases, examples
- [x] B1 schema linking examples + audit
- [x] B0 vs B1 comparison CSV/MD/plot/case_diff

## Smoke25
- [x] B0 predictions, metrics, summary, runlog, error_cases, examples
- [x] B1 predictions, metrics, summary, runlog, error_cases, examples
- [x] B1 schema linking smoke25 examples + audit
- [x] B0 vs B1 smoke25 comparison CSV/MD/plot/case_diff

## Aggregate
- [x] baseline_progression_smoke10_smoke25.csv/md/png
- [x] error_taxonomy_smoke25.md
- [x] b0_b1_failure_buckets.csv

## Tooling evidence
- [x] tools/notebook_tooling_audit.md
- [x] tools/run_cell_changelog.md
- [x] tools/bridge_status.md
- [x] tools/artifact_recheck.md
- [x] tools/tool_manifest.md
- [x] tools/tooling_readme.md

## Out of scope (intentionally not done)
- [ ] B2 Plan-SQL with retrieval
- [ ] Multi-DB subsets, dev-full evaluation
- [ ] Fine-tuning
- [ ] Final practice report writeup
- [ ] Final thesis chapter

## Practice tasks mapping
- See `practice/practice_tasks_mapping.md` for which task in the practice plan each artefact addresses.
'''
(PRACTICE / 'practice_evidence_checklist.md').write_text(checklist, encoding='utf-8')

# ============= practice/practice_tasks_mapping.md =============
mapping = f'''# Practice Tasks Mapping

Updated {ts}.

| Task in practice plan | Evidence on Drive | Status |
|---|---|---|
| Notebook + helper script audit | `outputs/logs/local_notebook_audit.md`, `outputs/logs/local_helper_script_audit.md`, `tools/notebook_tooling_audit.md`, `tools/run_cell_changelog.md` | completed |
| Runtime + Drive audit | `outputs/logs/runtime_project_root_audit.md`, `outputs/logs/bridge_status_drive.md` | completed |
| Spider asset acquisition + integrity | `outputs/logs/b0_blockers_audit.md`, `data/spider/SOURCE_AND_AUDIT.md` | completed |
| Loader + smoke subset construction | `outputs/logs/b0_loader_subsets_audit.md`, `outputs/logs/smoke25_subset_audit.md` | completed |
| B0 baseline (full schema, smoke10, smoke25) | `outputs/predictions/b0_spider_*.jsonl`, `outputs/metrics/b0_spider_*.csv`, `outputs/tables/b0_spider_*_summary.csv`, `outputs/tables/b0_spider_*_examples.md`, `outputs/tables/b0_spider_*_error_cases.md`, `outputs/logs/b0_spider_*_runlog.txt` | completed |
| B1 lexical schema linking implementation | `repo/src/evaluation/baselines.py`, `outputs/tables/b1_schema_linking_*examples.md`, `outputs/logs/b1_schema_linking_*audit.md` | completed |
| B1 baseline (reduced schema, smoke10, smoke25) | `outputs/predictions/b1_spider_*.jsonl`, `outputs/metrics/b1_spider_*.csv`, `outputs/tables/b1_spider_*_summary.csv`, `outputs/tables/b1_spider_*_examples.md`, `outputs/tables/b1_spider_*_error_cases.md`, `outputs/logs/b1_spider_*_runlog.txt` | completed |
| B0 vs B1 comparisons | `outputs/tables/b0_vs_b1_smoke{{10,25}}_comparison.{{csv,md}}`, `outputs/plots/b0_vs_b1_smoke{{10,25}}_bar.png`, `outputs/tables/b0_vs_b1_smoke{{10,25}}_case_diff.md` (smoke25 file is `b0_vs_b1_smoke25_case_diff.md`; smoke10 file is `b0_vs_b1_case_diff.md`) | completed |
| Aggregate progression | `outputs/tables/baseline_progression_smoke10_smoke25.{{csv,md}}`, `outputs/plots/baseline_progression_smoke10_smoke25.png` | completed |
| Error taxonomy | `outputs/tables/error_taxonomy_smoke25.md`, `outputs/tables/b0_b1_failure_buckets.csv` | completed |
| Bridge tooling for reproducibility | `tools/bridge_status.md`, `tools/exec_remote.py`, notebook cell `AGENT_BRIDGE_SETUP` (id `7f6bca53`) | completed |
| B2 (Plan-SQL, retrieval, validation, repair) | `outputs/logs/b2_readiness_after_smoke25.md`, `outputs/logs/b2_implementation_plan.md` | planned (not started) |
| Fine-tuning | — | out of scope |
| Final practice + thesis writeups | — | deferred |
'''
(PRACTICE / 'practice_tasks_mapping.md').write_text(mapping, encoding='utf-8')

# ============= practice/practice_figure_index.md =============
fig_index = f'''# Practice Figure Index

Updated {ts}.

| Path | Caption / role | Use |
|---|---|---|
| `outputs/plots/b0_vs_b1_smoke10_bar.png` | EX comparison B0 vs B1 on Spider smoke10 (n=10) | Section: smoke10 results |
| `outputs/plots/b0_vs_b1_smoke25_bar.png` | EX comparison B0 vs B1 on Spider smoke25 (n=25) | Section: smoke25 results |
| `outputs/plots/baseline_progression_smoke10_smoke25.png` | Aggregate EX progression across baselines and subsets | Section: progression analysis |

All plots are matplotlib bar charts at 140 DPI, generated reproducibly from the metrics CSVs.
'''
(PRACTICE / 'practice_figure_index.md').write_text(fig_index, encoding='utf-8')

# ============= practice/practice_table_index.md =============
tbl_index = f'''# Practice Table Index

Updated {ts}.

## Numeric tables (CSV)
| Path | Description |
|---|---|
| `outputs/metrics/b0_spider_smoke10_metrics.csv` | B0 single-row metrics on smoke10 |
| `outputs/metrics/b1_spider_smoke10_metrics.csv` | B1 single-row metrics on smoke10 (incl. avg_reduction_ratio) |
| `outputs/metrics/b0_spider_smoke25_metrics.csv` | B0 single-row metrics on smoke25 |
| `outputs/metrics/b1_spider_smoke25_metrics.csv` | B1 single-row metrics on smoke25 |
| `outputs/tables/b0_spider_smoke10_summary.csv` | B0 smoke10 key/value summary |
| `outputs/tables/b1_spider_smoke10_summary.csv` | B1 smoke10 key/value summary |
| `outputs/tables/b0_spider_smoke25_summary.csv` | B0 smoke25 key/value summary |
| `outputs/tables/b1_spider_smoke25_summary.csv` | B1 smoke25 key/value summary |
| `outputs/tables/b0_vs_b1_smoke10_comparison.csv` | B0 vs B1 head-to-head on smoke10 |
| `outputs/tables/b0_vs_b1_smoke25_comparison.csv` | B0 vs B1 head-to-head on smoke25 |
| `outputs/tables/baseline_progression_smoke10_smoke25.csv` | All four runs side by side |
| `outputs/tables/b0_b1_failure_buckets.csv` | Error bucket counts per baseline (smoke25) |

## Narrative tables (Markdown)
| Path | Description |
|---|---|
| `outputs/tables/b0_spider_smoke{{10,25}}_examples.md` | First 5 predictions per baseline as a table |
| `outputs/tables/b0_spider_smoke{{10,25}}_error_cases.md` | Wrong predictions per baseline (≤20) |
| `outputs/tables/b1_spider_smoke{{10,25}}_examples.md` | Same, with selected_tables column |
| `outputs/tables/b1_spider_smoke{{10,25}}_error_cases.md` | Same |
| `outputs/tables/b1_schema_linking_examples.md` | Per-question linking output (smoke10) |
| `outputs/tables/b1_schema_linking_smoke25_examples.md` | Per-question linking output (smoke25) |
| `outputs/tables/b0_vs_b1_smoke10_comparison.md` | Counts of improvements / regressions / unchanged on smoke10 |
| `outputs/tables/b0_vs_b1_smoke25_comparison.md` | Same on smoke25 |
| `outputs/tables/b0_vs_b1_case_diff.md` | At least 5 paired cases on smoke10 |
| `outputs/tables/b0_vs_b1_smoke25_case_diff.md` | At least 5 paired cases on smoke25 |
| `outputs/tables/baseline_progression_smoke10_smoke25.md` | Conclusion sentence with deltas |
| `outputs/tables/error_taxonomy_smoke25.md` | Bucket definitions + per-cell breakdown |
'''
(PRACTICE / 'practice_table_index.md').write_text(tbl_index, encoding='utf-8')

# ============= outputs/logs/thesis_experiment_inventory.md =============
LOGS = OUTPUTS / 'logs'
thesis_inventory = f'''# Thesis Experiment Inventory

Updated {ts}.

## Baselines implemented
- **B0** — full-schema NL→SQL prompt, Qwen2.5-Coder-7B-Instruct, 4-bit nf4 bitsandbytes, greedy decoding, max_new_tokens=192. SQL extracted with regex; executed via SQLite with 8 s timeout (`func_timeout`).
- **B1** — same model and decoding, but the schema in the prompt is reduced via lexical schema linking. Token-overlap scoring: table-name match weighted 2, column-name match weighted 1, English stopwords removed, `min_score = 0.5`. Tables with no signal trigger a fallback to the full schema.

## Subsets evaluated
- `data/spider/subsets/smoke_10.json` (n=10, all `concert_singer`)
- `data/spider/subsets/smoke_25.json` (n=25, all `concert_singer`, smoke10 ⊂ smoke25)
- `data/spider/subsets/smoke_50.json` exists on Drive but not yet evaluated.
- Full Spider dev (n=1034) not yet evaluated.

## Metrics computed
- **EX** (Execution Match): predicted SQL executes and returns the same row multiset as gold SQL on the SQLite DB.
- **Executable count**: predicted SQL parses and executes without exception (independent of correctness).
- **Avg schema reduction ratio (B1)**: |selected tables| / |all tables in DB|, averaged across questions.
- **Fallback count (B1)**: questions where no token signal was found and B1 used the full schema.

## Comparisons produced
- B0 vs B1 head-to-head on each subset (CSV, MD narrative, bar plot PNG, case_diff MD).
- Aggregate progression smoke10 → smoke25 (CSV, MD narrative + delta + conclusion sentence, 4-bar PNG).
- Error taxonomy on smoke25 with 8 buckets and per-cell breakdown (MD + counts CSV).

## Reproducibility evidence
- Spider source provenance: `data/spider/SOURCE_AND_AUDIT.md`
- Subset audits: `outputs/logs/b0_loader_subsets_audit.md`, `outputs/logs/smoke25_subset_audit.md`
- Runtime + GPU + library versions: `outputs/logs/runtime_project_root_audit.md`
- Per-run logs: `outputs/logs/{{b0,b1}}_spider_*_runlog.txt`
- Bridge tooling state: `outputs/logs/bridge_status_drive.md`, `outputs/logs/artifact_recheck_drive.md`
- Tooling audit: `tools/notebook_tooling_audit.md`, `tools/run_cell_changelog.md`

## Limitations to disclose in the chapter
- Only one DB (`concert_singer`) is touched by smoke10/smoke25, so schema-linking benefit is bounded — most signal exists between *different* DBs, not within one.
- 4-bit quantisation may shift behaviour relative to fp16/bf16; not measured here.
- Single greedy decoding (no sampling, no self-consistency).
- No retrieval, planner, or repair loop yet (those belong to B2+).
- EX is execution-only; no logical-form / exact-match metric.
'''
(LOGS / 'thesis_experiment_inventory.md').write_text(thesis_inventory, encoding='utf-8')

# ============= outputs/logs/thesis_figure_index.md =============
thesis_fig = f'''# Thesis Figure Index

Updated {ts}.

| Suggested fig label | Path | Caption draft |
|---|---|---|
| Fig. baseline_smoke10 | `outputs/plots/b0_vs_b1_smoke10_bar.png` | "Execution Match (EX) of the full-schema baseline (B0) versus the reduced-schema baseline (B1) on Spider smoke10 (n=10), Qwen2.5-Coder-7B-Instruct, greedy decoding." |
| Fig. baseline_smoke25 | `outputs/plots/b0_vs_b1_smoke25_bar.png` | "EX of B0 versus B1 on Spider smoke25 (n=25); same model and decoding." |
| Fig. progression | `outputs/plots/baseline_progression_smoke10_smoke25.png` | "Aggregate EX progression of B0 and B1 across smoke10 and smoke25." |

All figures rendered at 140 DPI from the corresponding `outputs/metrics/*.csv`. The notebook cells that produce them (and their inputs) are tracked under `tools/remote_scripts/05_smoke25_comparison_and_aggregate.py` (smoke25 plot) and the original B1 pipeline cell (smoke10 plot).
'''
(LOGS / 'thesis_figure_index.md').write_text(thesis_fig, encoding='utf-8')

# ============= outputs/logs/thesis_table_index.md =============
thesis_tbl = f'''# Thesis Table Index

Updated {ts}.

| Suggested table label | Path | Notes |
|---|---|---|
| Tbl. metrics_summary | `outputs/tables/baseline_progression_smoke10_smoke25.csv` | Side-by-side EX, executable_count, avg reduction across all four runs. Camera-ready: rename columns. |
| Tbl. smoke10_compare | `outputs/tables/b0_vs_b1_smoke10_comparison.csv` | B0 vs B1 head-to-head + transition counts on smoke10. |
| Tbl. smoke25_compare | `outputs/tables/b0_vs_b1_smoke25_comparison.csv` | Same on smoke25. |
| Tbl. failure_buckets | `outputs/tables/b0_b1_failure_buckets.csv` | Counts per error bucket across baselines on smoke25. |
| Tbl. linking_examples_smoke10 | `outputs/tables/b1_schema_linking_examples.md` | Per-question linking on smoke10 with selected tables and reduction ratio. |
| Tbl. linking_examples_smoke25 | `outputs/tables/b1_schema_linking_smoke25_examples.md` | Same on smoke25. |
| Tbl. case_diff_smoke25 | `outputs/tables/b0_vs_b1_smoke25_case_diff.md` | ≥5 paired cases with verdict + comment. |

The MD case-diff and examples tables are agent-generated narratives; for the chapter they should be tightened by hand and trimmed to top cases that illustrate the failure modes worth discussing.
'''
(LOGS / 'thesis_table_index.md').write_text(thesis_tbl, encoding='utf-8')

# ============= outputs/logs/thesis_methods_notes.md =============
thesis_methods = f'''# Thesis Methods Notes

Sketches of phrasing the thesis chapter can re-use. Not the chapter itself.

## Setup paragraph
Spider dev split was loaded from the official YALE bundle; we sampled the first 10 and 25 examples to define `smoke_10` and `smoke_25`. Both subsets fall in the `concert_singer` database (4 tables). All inference was run on a single NVIDIA L4 GPU in Google Colab, using `Qwen/Qwen2.5-Coder-7B-Instruct` quantised to 4-bit `nf4` via `bitsandbytes`, with greedy decoding (`do_sample=False`) and `max_new_tokens=192`. Generated SQL was extracted with a regex stripping markdown fences, executed against SQLite with an 8-second timeout via `func_timeout`, and compared to gold by row-multiset equality.

## Baselines paragraph
**B0** receives the full schema as plaintext (`Database: <db>` followed by one line per table listing its columns). **B1** uses the same prompt scaffold but replaces the schema block with a reduced one. Reduction is computed by *lexical schema linking*: for each table and column name, count tokens shared with the question (lowercase, English stopwords removed); each table-name match contributes 2 to the score, each column-name match contributes 1. Tables with score ≥ 0.5 are kept. If no table scores above the threshold, B1 falls back to the full schema (recorded in `fallback_full_schema_count`).

## Results-shape paragraph
On `smoke_10`, B0 and B1 both reach EX=1.0 (10/10 executable). B1 keeps on average **{(b1_10.get("avg_reduction_ratio") if b1_10 else "?")}** of the full schema and falls back to full schema on **{(b1_10.get("fallback_full_schema_count") if b1_10 else "?")}** of 10 questions. On `smoke_25`, the corresponding numbers are EX_B0={b0_25.get("ex") if b0_25 else "?"} and EX_B1={b1_25.get("ex") if b1_25 else "?"} with avg reduction **{(b1_25.get("avg_reduction_ratio") if b1_25 else "?")}** and **{(b1_25.get("fallback_full_schema_count") if b1_25 else "?")}** fallbacks. Side-by-side counts of improvements, regressions, and unchanged outcomes are in `b0_vs_b1_smoke{{10,25}}_comparison.csv`.

## Limitations paragraph
The schema-linking signal is bounded on this evaluation: smoke10 and smoke25 both probe a single database with four tables, so the upper bound for the linker's contribution is small (irrelevant tables are at most 3 of 4). Stronger conclusions require a multi-DB subset where the linker can rule out *databases*, not just tables. EX is execution-equivalence only; logical equivalence and partial-credit metrics are not computed. The model is loaded in 4-bit; numerical sensitivity to the quantisation scheme is not measured. No retrieval, planner, or repair loop is integrated yet — these belong to B2.

## Tooling paragraph (for the methods appendix)
Inference cells are dispatched via a Cloudflare-tunnelled Flask server inside the Colab kernel (notebook cell `AGENT_BRIDGE_SETUP`, id `7f6bca53`). The local agent talks to the kernel directly over HTTPS; this avoids the focus-race failure of SendKeys-based notebook drivers when the agent's terminal output is rendered in the same VS Code window as the notebook. Predictions are saved incrementally so that a Cloudflare HTTP timeout (~100 s) in the middle of inference does not lose data; the background thread continues writing on Drive after the request returns.
'''
(LOGS / 'thesis_methods_notes.md').write_text(thesis_methods, encoding='utf-8')

print('practice and thesis evidence packs written')
print('practice files:', sorted(p.name for p in PRACTICE.iterdir()))
print('thesis files in logs:', sorted(p.name for p in LOGS.iterdir() if p.name.startswith('thesis_')))
print('STATUS=DONE')
