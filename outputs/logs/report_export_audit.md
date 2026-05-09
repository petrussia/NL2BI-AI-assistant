# Report export audit

**Generated:** 2026-04-30T19:42:45.696599+00:00
**Source root:** `/content/drive/MyDrive/diploma_plan_sql/outputs`

## Inventory snapshot
- metrics CSVs: 98
- predictions JSONL: 98
- plots PNG: 16
- bundled docs: 10
- thesis_pack_shubin files: 17

## What goes into the export pack
- Headline numbers from `final_experiment_master_matrix.csv` (authoritative)
- 5 master narrative files in `01_master/`
- 2 condensed numbers files in `02_numbers/`
- ~10 most insertable tables in `03_tables/`
- ~6 plots that actually belong in the joint VKR (not all 17+)
- 9 ready-to-paste Russian text blocks in `05_text_blocks/`
- Shortlist of evidence files (predictions/metrics) — not all 88
- Architecture + operations + IO contracts in `07_design_and_arch/`

## What is intentionally NOT in the export pack
- 88 raw metric CSVs (only headline aggregations bubble up)
- Spider2-Lite raw `resource/` (already excluded from main mirror)
- BIRD raw .sqlite + .zip (~1 GB, already on Drive only)
- Historic v0/v1/legacy run files (only canonical strongest versions are bubbled up)
- All blocker noise — only the canonical DeepSeek blocker artifact
