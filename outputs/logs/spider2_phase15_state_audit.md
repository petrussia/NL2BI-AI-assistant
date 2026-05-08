# Spider2 Phase 15 — state audit

_Generated: 2026-05-08 | branch: `experiments/denis`_

## Git
- HEAD = `0a8b433` (Phase 14)
- Last 3: `0a8b433` / `2b95742` / `44a4d23`
- All commits LOCAL-ONLY (no push triggered, no push without explicit user command).

## Live infra
- Bridge `chassis-tracked-scanned-britney.trycloudflare.com` → pid 6135 ✅
- BigQuery live ✅
- Snowflake live ✅

## Phase 14 artefacts present
- `repo/src/evaluation/spider2_snow_v12_colab_runner.py` ✅
- `repo/src/evaluation/spider2_lite_bq_v11_colab_runner.py` ✅
- `repo/src/evaluation/spider2_bq_schema_grounding_v11.py` ✅
- `outputs/REPORT_SPIDER2_V12.md` ✅

## Carried-forward pilot results
- Spider2-DBT FULL 68: task_success 9/68 = **13.2%** (Phase 11) — only publishable.
- Spider2-Snow v11 pilot10: schema_valid 1/10 (rich render).
- Spider2-Snow v12 pilot10: schema_valid 0/10 (strict compact render — REGRESSION).
- Spider2-Lite-BQ v11 pilot10: schema_valid 0/10. Validator has TWO known false-positive classes:
  - 4-part `project.project.dataset.table` (model duplicates project) → not collapsed by current normalizer.
  - STRUCT field access `event_params.key` → flagged as unknown column.

## Phase 15 plan
1. **Snow v13** = rich render (v11) + 3-round repair (v12) + alias-aware validator + external_knowledge injection.
2. **BQ v12 validator** = wildcard table support (`events_*`) + 4-part collapse for repeated project + STRUCT/UNNEST awareness (don't flag nested-field access as unknown column) + dash-aware identifier parsing.
3. Pilots gated at 30% schema_valid → pilot30 → 50% → FULL.
4. INT4 32B sanity ONLY if schema_valid ≥ 20-30%.
5. Reports + commit (no push).

## Concrete failures from BQ v11 pilot10 (root cause memo input)
Example task `bq011`: model emitted
`bigquery-public-data.bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20201107`
— 4-part with project doubled. Validator should collapse `A.A.B.C → A.B.C`.
Same SQL referenced `event_params.key` and `event_params.value.int_value`
— BigQuery struct/array access; validator treats `event_params` as a
table alias and `key` as an unknown column. Need to skip column
validation when qualifier matches a column name in the FROM tree.
