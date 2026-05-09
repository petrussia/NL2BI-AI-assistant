# Spider2 v18 — STEP 1 live catalog audit

_Generated: 2026-05-09 | branch: `experiments/denis`_

## Scope

Refresh both BQ and Snowflake metadata via live `INFORMATION_SCHEMA`
queries. Replaces the year-old Spider2 author snapshot that drove the
Phase 16 catalog/live divergence (5/6 BQ schema-valid candidates failed
`dry_run` with `object_not_found`).

## BQ live catalog

| field | value |
|---|---:|
| Spider2-Lite-BQ aliases | 74 |
| project.dataset combos | 154 |
| GCP projects covered | 10 (`bigquery-public-data`, `data-to-insights`, `fh-bigquery`, `firebase-public-project`, `isb-cgc`, `isb-cgc-bq`, `mitelman-db`, `open-targets-genetics`, `open-targets-prod`, `spider2-public-data`) |
| `INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` rows (incl. nested) | **422,562** |
| `INFORMATION_SCHEMA.TABLES` rows | **5,859** |
| query errors | 3 |
| jsonl size | 133 MB |
| canonical path | `outputs/cache/spider2_bq_live_catalog_v18.jsonl` |
| log | `outputs/cache/spider2_bq_live_catalog_v18.log` |

## Snowflake live catalog

| field | value |
|---|---:|
| Spider2-Snow databases queried | 152 |
| `INFORMATION_SCHEMA.COLUMNS` rows | **572,997** |
| `INFORMATION_SCHEMA.TABLES` rows | **13,473** |
| query errors | 2 |
| jsonl size | 160 MB |
| canonical path | `outputs/cache/spider2_snow_live_catalog_v18.jsonl` |
| log | `outputs/cache/spider2_snow_live_catalog_v18.log` |

## Coverage notes

- BQ uses `INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` instead of plain
  `COLUMNS` so nested struct/array paths are addressable directly. This
  fixes the Phase 14-16 struct-field FP problem at retrieval time:
  `event_params.key`, `event_params.value.string_value` etc. now appear
  as first-class records.
- Snow uses unquoted `INFORMATION_SCHEMA.COLUMNS` per database, with
  `TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')` to skip self-meta.
- Errors are recorded inline as `{"kind":"error", ...}` records rather
  than dropping silently — see harvest scripts.

## Reproducibility

```sh
python tools/harvest_bq_live_catalog_v18.py --poll-every 30
python tools/harvest_snow_live_catalog_v18.py --poll-every 30
```

Both scripts are idempotent: each run truncates the previous output,
streams to Drive, and pulls the result locally on completion.

## Why this was the highest-leverage v18 step

Phase 16 root-cause audit attributed 95.7% of historical task-attempt
failures to true_hallucination. Phase 17 confirmed bigger generators
do not fix this in open vocabulary. The next-step bottleneck identified
by Phase 16's parse_ok=0 finding was **catalog/live divergence**: even
when constrained substitution lifted schema_valid 1/10 → 6/10, BQ live
`dry_run` rejected 5/6 with `object_not_found` because the Spider2
snapshot identifiers had drifted from production.

Refreshing the catalog was therefore the first move that *could*
re-enable a non-zero `dry_run`/`execute_ok` signal. With the live
catalog in place, the v18 schema-first pipeline now has a closed
identifier vocabulary that BQ will actually accept.
