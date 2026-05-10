# Spider2-Lite-BQ v21 pilot50 — failure audit (STAGE A1)

_Generated: 2026-05-10 | source: `outputs/spider2_lite/runs/lite_bq_v21_pilot50/traces.jsonl`_

## Headline

Across **50 chosen candidates** in v21 pilot50:

| outcome | count | rate |
|---|---:|---:|
| chosen schema_valid | 25 | 50% |
| chosen dry_run_ok | 22 | 44% |
| chosen schema_valid AND dry_run_ok ("true ok") | 12 | 24% |
| schema_valid only (BQ engine rejects) | 13 | 26% |
| dry_run_ok only (validator false-positive reject) | **10** | **20%** |
| neither | 15 | 30% |

The **10 "dry_run_ok only"** cases are the smoking gun for STAGE A2:
all 10 have AST validator marking them `schema_invalid` (with leaks
like `col:event_timestamp`, `col:transactionRevenue`, `col:pageviews`)
while BigQuery accepts them. Cause: pack column lists are too thin —
the BM25 linker keeps only top-scoring columns, so legitimate field
references don't appear in `pack.tables[*].columns` and the validator
treats them as out-of-pack.

## Per-task chosen-candidate failure category

`outputs/logs/spider2_v22_bq_failure_audit.csv` for the per-row table.

| category | count | n_dr_ok_within | description |
|---|---:|---:|---|
| ast_leak | 24 | **10** | validator false positive — column not in pack-top-K but real |
| ok | 12 | 12 | true wins |
| multi_table_or_unknown_name | 5 | 0 | planner refers to a table not in the FROM clause; needs join-aware renderer |
| multi_level_unnest | 2 | 0 | `hits.product.field` where `hits.product` itself is ARRAY<STRUCT> |
| nested_aggregate | 2 | 0 | `SUM(SUM(x)/SUM(y))` patterns; need WITH staging |
| no_signature | 2 | 0 | operator AND with int operand etc.; type-aware fix |
| function_not_found | 1 | 0 | `ARRAY_CONTAINS` (not BQ standard); needs rewrite to `EXISTS UNNEST` |
| group_by_window_raw | 1 | 0 | window function + raw cols missing GROUP BY |
| parse_error | 1 | 0 | edge case — UNION ALL pattern |

## Pack-thinness observation

For bq009 (one of the false-positive cases): the recall stats show
the linker indexed 422,562 columns and chose top scores per table,
but the resulting **pack has only 8 columns total** across 8 tables
(token budget 1033). `totals.transactionRevenue` — the column the
planner correctly used and BQ accepted — is not in the pack at all,
despite being a real top-level GA Analytics field.

This is not a planner bug, not a renderer bug, and not a validator
bug per se — it is the closed-set discipline being too tight: the
validator enforces residency against the prompt-trimmed pack, but
the planner often correctly references columns that exist in the
actual table schema even when they didn't make the prompt-pack.

## Recommended fix (STAGE A2)

1. Extend `schema_pack_builder_v18` to include a side-channel field
   per table: `all_columns: list[str]` — full column-name set from
   the live catalog. Not used for planner prompting (compact pack
   stays compact) — only consumed by `candidate_selector_v18` for
   residency check.
2. Validator's `_normalize_pack_names` then unions `pack.tables[*].columns`
   AND `pack.tables[*].all_columns` for the residency sets.
3. Expected effect: ~10 of the 24 ast_leak chosen candidates flip to
   `ok` (already pass dry_run); chosen_schema_valid rises 50% → ~70%.
   That alone would clear the FULL gate (≥60%).

Plus separately:
- STAGE A2 join_hints population for the 5 multi-table cases →
  potentially +5pp dry_run_ok.
- STAGE A3 Family C deterministic JOIN renderer to actually
  exploit the join_hints.

## What this audit settles

The 4-session pilot50 stability (sv 50-52%, exec 42-46%) does NOT
mean the pipeline is at its modeling ceiling. **20pp of "phantom
unwins" exist** because the validator over-rejects pack-thin cases
the engine accepts. STAGE A2 is the specific lever to recover them.
