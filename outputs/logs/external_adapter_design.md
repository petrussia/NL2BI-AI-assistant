# External benchmark adapter — design

**Module:** `repo/src/evaluation/external_benchmark_adapters.py`

## Public API
- `bird_load(slice_path)` — load BIRD slice (list of dict).
- `bird_db_path(db_id) -> Path` — resolves to `external_benchmarks/bird_mini_dev/raw/minidev/minidev/MINIDEV/dev_databases/<db_id>/<db_id>.sqlite`.
- `bird_full_schema(db_id)` — builds Spider-style schema text from `dev_tables.json`.
- `bird_lex_link(question, db_id)` — same lex-overlap linker as our internal Spider linker.
- `bird_reduced_schema(db_id, selected_idx)` — reduced schema for B1 fallback.
- `spider2_load(slice_path)` — load Spider2-Lite slice.
- `spider2_full_schema_proxy(db)` — synthesises a schema description from DDL.csv + sample JSON files in `resource/databases/sqlite/<db>/` (or bigquery/snowflake DDL as fallback).
- `spider2_lex_link_proxy(question, db)` — proxy lex linker over the synthesised schema.
- `structural_features(sql) / aggregate_structural(records)` — execution-free metrics for prediction-only benchmarks.

## Why two paths
- BIRD ships SQLite databases → full EX execution via our standard sandbox (`func_timeout`, 8s).
- Spider 2.0-Lite ships DDL+JSON for BigQuery/Snowflake — no actual database engine instance, no public gold inside the lite jsonl. We compute structural metrics only and document this as an environmental limitation.

## Integration with main pipeline
- Prefix-based naming: `<baseline>_<model_slug>_<benchmark>_<subset>` (e.g. `b0_qwen2p5_coder_7b_bird_minidev_30`).
- All outputs land in the same `outputs/{predictions,metrics,tables,logs}/` directories.
- Master matrix gets a new column `benchmark_group ∈ {internal_core, external_validation}` to keep external slices separate from canonical Spider runs.
- A separate `external_validation_master_matrix` view aggregates only the external rows.
