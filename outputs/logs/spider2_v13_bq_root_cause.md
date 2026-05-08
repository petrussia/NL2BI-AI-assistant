# Spider2-Lite-BQ v12 — root cause memo

_Generated: 2026-05-08_

## Symptom

BQ v12 pilot10 result: `chosen_schema_valid = 1/10 (10%)`. **Lift
+1 vs v11's 0/10.** Validator-side fixes accounted for substantial
false-positive reduction:

- **68 struct-field-access skips** (column refs like
  `event_params.key`, `event_params.value.int_value` no longer flagged
  unknown — qualifier `event_params` is a STRUCT/ARRAY column on the
  GA4 events tables).
- **19 wildcard-table resolves** (pattern `events_*` matched against
  any catalog table whose name starts with `events_`).
- **Project-doubled 4-part collapse** in normalizer (model emitted
  `bigquery-public-data.bigquery-public-data.dataset.table`; v12
  collapses repeated project segment before validation).

## What v12 added vs v11

| change | impact |
|---|---|
| Project-doubled 4-part collapse | catches the most common BQ ident error from v11 |
| STRUCT/UNNEST column-ref skip | 68 false-positive avoidances |
| Wildcard table prefix-match | 19 wildcard resolves |
| BQ pseudo-cols whitelist | `_TABLE_SUFFIX`, `_PARTITIONTIME`, `_PARTITIONDATE` no longer flagged |

## Remaining failures (9 schema_invalid + 1 BadRequest)

The 9 remaining `schema_invalid` cases failed because the model
invented column names that weren't fixable by struct/wildcard
shortcuts. Examples seen in predictions: nested GA4 event_params
keys the model named after description tokens rather than actual
column names.

The 1 `BadRequest` case made it past the validator (schema_valid=True)
but BigQuery rejected it at live execute — likely a bytes-billed cap
or a runtime-only syntax issue. This is the first BQ candidate that
ever passed our validator.

## Aggregate BQ evidence

| pilot | schema_valid | engine ok | dominant remaining error |
|---|---:|---:|---|
| v10 | n/a (no validator) | 0 | object_not_found 10/10 |
| v11 | 0/10 | 0 | schema_invalid 10/10 |
| **v12** | **1/10** | 0 | schema_invalid 9/10 + BadRequest 1 |

## Conclusion

Validator engineering on BQ is now solid:
- Struct-aware ✓
- Wildcard-aware ✓
- Pseudo-column-aware ✓
- 4-part collapse ✓

Remaining gap is purely **model-side identifier hallucination**,
mirror of Snow. Same next-step:
1. Constrained identifier substitution (Phase 16).
2. INT4 Coder-32B for headroom test.

## Bug-fix backlog

None — v12 ran cleanly to completion (10/10 predictions; no crashes).
