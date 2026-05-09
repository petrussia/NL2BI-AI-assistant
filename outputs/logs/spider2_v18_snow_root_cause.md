# Spider2 v18 — Snow root-cause read (catalog-only)

_Generated: 2026-05-09_

## Status

Snow live catalog harvested (152 DBs, 572,997 columns, 13,473 tables;
160 MB at `outputs/cache/spider2_snow_live_catalog_v18.jsonl`).
**Snow pilot10 NOT run this session** — deferred per the audited scope
cut (end-to-end thin slice on BQ first; Snow second).

## What the v18 catalog refresh changes for Snow

Phase 11–17 Snow runs all bottomed at 0–1/10 schema_valid. Phase 16 root
cause attributed this to **semantic** identifier hallucination
(database/schema-level miss) rather than typo-shaped errors. The Snow
catalog in the Spider2 author snapshot ships ~152 DBs but the column
metadata is partial; many tasks reference column or table names that
*do* exist in live Snowflake but were not in the JSON catalog.

The v18 live harvest now provides:
- 572,997 column records vs the few thousand the static catalog held
- COMMENT / description fields where present
- TABLE_TYPE + ROW_COUNT + BYTES — useful for re-ranking by table
  importance during schema linking

## Hypothesis to test in v18.1 (Snow pilot10)

Same v18 pipeline, lane=snow. Predictions:
- Schema linker recall on Snow will be HIGH because the live catalog
  is dense — the pack should reliably contain the gold table in top-K.
- The structured planner's identifier residency check should pass at
  much higher rate than on BQ because Snow uses unhyphenated DB names
  (no `bigquery-public-data` strawman issue).
- `parse_ok` should hit ≥80% (the deterministic renderer eliminates
  syntax errors).
- `execute_ok` (Snow `EXPLAIN`/`DESCRIBE` or actual run with
  `MAX_ROWS=0` cap) is the open question — bullish on 1-3/10 if the
  three v18.1 BQ patches port cleanly.

## What the catalog log already tells us

- 2 query errors out of 152 — both connect-level. The remaining 150 DBs
  harvested cleanly via `INFORMATION_SCHEMA.COLUMNS / TABLES`.
- The largest DB by column count is in the analytics demo family;
  Spider2 questions on those DBs should benefit most from the dense
  metadata.

## Action

Snow v18 pilot is the **first move of v18.1**, immediately after the
three BQ patches in §13 of `REPORT_SPIDER2_V18.md` are landed. No
further Snow data work needed; the catalog is ready.
