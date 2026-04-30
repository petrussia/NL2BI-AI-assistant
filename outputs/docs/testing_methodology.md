# Testing Methodology

Date: 2026-04-29T15:03:36.172745+00:00.

## Datasets and subsets

| Subset | n | Description | Reproducibility |
|---|---|---|---|
| `smoke_10` | 10 | first 10 dev items, all `concert_singer` | `dev[:10]` |
| `smoke_25` | 25 | first 25 dev items, all `concert_singer` (smoke10 ⊆ smoke25) | `dev[:25]` |
| `smoke_50` | 50 | first 50 dev items | `dev[:50]` (not yet evaluated) |
| `multidb_30` | 30 | 5 first items from each of 6 DBs (sorted alphabetically, excluding `concert_singer`); deterministic | see `outputs/logs/multidb_30_audit.md` |
| Spider dev (full) | 1034 | full dev split | not evaluated this iteration |

## Primary metric

**EX (Execution Match)** = `1` if predicted SQL executed against gold DB returns the same row multiset as gold SQL, else `0`. Aggregated over a subset as the mean.

## Auxiliary metrics

- `executable_count` — how many predicted SQLs executed without raising.
- `plan_valid_count` — for B2/B3/B4: how many plans validated against `plan_schema*.json`.
- `plan_parse_failures` — JSON could not even be parsed.
- `avg_reduction_ratio` — for B1/B3/B4: mean fraction of full schema kept by the linker.
- `fallback_full_schema_count` — linker gave up and used full schema.
- `retrieval_hit_count` — for B1R/B2R: top-1 retrieved DB == gold DB.
- `repaired_count` — for B4-lite: items where bounded repair was triggered.
- `rejected_unsafe_total` — for B4-lite: candidates dropped by SELECT-only guard.

## Execution policy

- SQL executed via `sqlite3` against the gold DB file in `data/spider/database/<db_id>/<db_id>.sqlite`.
- Per-query timeout: **8 seconds** via `func_timeout`. Exceeded → `error_type=timeout`.
- Row comparison: `sorted(pred_rows) == sorted(gold_rows)` (multiset equality, no ordering requirement). Tuple equality, no type coercion beyond what SQLite does natively.

## Sandbox limits

- All execution happens against read-only Spider DB files.
- Validation gate (B4-lite) blocks DDL/DML before execution.
- Per-query timeout prevents infinite loops / accidental cross-product blowup.

## Ablation procedure

For each baseline (B0, B1, B2, B2_v1, B3, B3_v1, B4-lite, B4_final):
1. Generate per-item prediction → predictions JSONL.
2. Compute aggregate metrics → metrics CSV.
3. Render summary, run-log, error-cases, examples → tables/.
4. Compare against the previous baseline in the ladder → comparison CSV/MD/PNG.

For each model in the matrix (Qwen-Coder, Qwen-Instruct, Llama, DeepSeek):
- Run at minimum B0 + B1 on `smoke_10`.
- Optionally run B2_v1 on `smoke_10` if compute budget allows.

For multi-DB:
- Run B0, B1, B2_v1, B3_v1, B4_final on `multidb_30`.

## Reproducibility evidence

Every run produces:
- `outputs/predictions/<run_id>_predictions.jsonl` — per-item raw + parsed.
- `outputs/metrics/<run_id>_metrics.csv` — aggregate metrics single-row.
- `outputs/logs/<run_id>_runlog.txt` — checkpoints, timings, model id, quantization.
- `outputs/tables/<run_id>_summary.csv`, `_examples.md`, `_error_cases.md`.

Bridge tooling and audits:
- `outputs/logs/runtime_project_root_audit.md` — versions of torch / transformers / accelerate / bitsandbytes / datasets / pandas / GPU.
- `outputs/logs/bridge_status_drive.md` — bridge endpoint and probes.
- `outputs/logs/artifact_recheck_drive.md` — pre-run recheck of required artefacts.
- `data/spider/SOURCE_AND_AUDIT.md` — Spider source provenance and integrity.

## Comparison artefacts

For each pairwise comparison (B0 vs B1, B0 vs B1 vs B2, multidb ablation, etc.):
- `<comparison>_comparison.csv` — head-to-head numbers.
- `<comparison>_comparison.md` — narrative + transition counts (improvements / regressions / unchanged).
- `<comparison>_bar.png` — bar chart of EX values.
- `<comparison>_case_diff.md` — at least 5 paired cases with verdict + comment.

## Failure-mode taxonomy (smoke25)

8 buckets, defined in `outputs/tables/error_taxonomy_smoke25.md`:
`unchanged_correct` / `syntax_or_runtime_error` / `sqlite_timeout` / `wrong_join_or_table` / `wrong_aggregation` / `wrong_filter_or_predicate` / `result_mismatch_subtle` / `unexpected`.
