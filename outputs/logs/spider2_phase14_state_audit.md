# Spider2 Phase 14 — state audit

_Generated: 2026-05-08 | branch: `experiments/denis`_

## Git state
- HEAD = `2b95742` (Phase 13)
- Last commits: `2b95742` / `44a4d23` / `09abb5a` / `a5cdbfe` / `ac84d20`
- All four Spider2 phase commits are LOCAL-ONLY (no push attempted, no
  push will be triggered without explicit user approval).

## Live infra
- Bridge `chassis-tracked-scanned-britney.trycloudflare.com` → pid 6135 ✅
- BigQuery live ✅ (project `project-0e0fc8a5-…`)
- Snowflake live ✅ (PARTICIPANT/COMPUTE_WH_PARTICIPANT)

## Phase 13 artefacts present (15/15)
- `outputs/REPORT_SPIDER2_V11.md`
- `outputs/tables/spider2_full_master_matrix_v11.{csv,md}`
- `outputs/tables/spider2_full_lane_breakdown_v11.csv`
- `outputs/tables/spider2_full_error_taxonomy_v11.csv`
- `outputs/logs/spider2_v11_scientific_findings.md`
- `outputs/logs/spider2_v11_production_recommendation.md`
- `outputs/predictions/spider2_lite_bq_v10_pilot10_predictions.jsonl`
- `outputs/predictions/spider2_snow_v11_snow_v11_pilot10_predictions.jsonl`
- `repo/src/evaluation/spider2_snow_catalog_v11.py`
- `repo/src/evaluation/spider2_snow_schema_grounding_v11.py`
- `repo/src/evaluation/spider2_snow_v11_colab_runner.py`
- `repo/src/evaluation/spider2_lite_bq_v10_colab_runner.py`
- `tools/run_spider2_lite_bq_v10_pilot.py`
- `tools/run_spider2_snow_v11_pilot.py`

No restoration needed. Proceeding to STEP 1.

## Pilot results carried forward
- Spider2-DBT FULL 68 (Phase 11): task_success 9/68 = 13.2% — only
  publishable Spider2 number.
- Spider2-Lite-BQ v10 pilot10: parse_ok 0/10, 10/10 `object_not_found`.
- Spider2-Snow v11 pilot10: schema_valid 1/10 (10%), parse_ok 0/10,
  9/10 `schema_invalid`, 1/10 `syntax`. v10→v11: object_not_found at
  engine 7→0; schema_valid 0→1.

## Phase 14 plan
1. STEP 1 — BQ schema-grounding v11 (catalog + validator + repair + runner + pilot10)
2. STEP 2 — Snow v12 (strict render + multi-round repair + alias-aware validator + pilot10)
3. STEP 3 — Lite-SF v12 only if Snow v12 gate ≥30%
4. STEP 4 — INT4 32B sanity only if schema pipeline works but model is bottleneck
5. STEP 5 — REPORT_SPIDER2_V12.md + tables + logs
6. STEP 6 — commit Phase 14 (no push)
