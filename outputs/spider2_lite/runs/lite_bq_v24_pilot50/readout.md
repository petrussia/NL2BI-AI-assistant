# Spider2-Lite-BQ v24 — `lite_bq_v24_pilot50` (Phase 24 sequential)

| metric | value | rate |
|---|---:|---:|
| n_total | 50 | — |
| plan_validation_ok | 27 | 54.0% |
| chosen_schema_valid | 27 | 54.0% |
| parse_ok | 49 | 98.0% |
| execute_ok (BQ dry_run) | 22 | 44.0% |

## Family choice

| family | count | rate |
|---|---:|---:|
| `A` | 43 | 86.0% |
| `B` | 7 | 14.0% |

## Engine rewrite emit + helpful counts

| kind | emitted | helpful (won dry_run) |
|---|---:|---:|
| `array_contains` | 1 | — |

Total rewrite-helpful (any kind): 0

## Error taxonomy

| error_class | count |
|---|---:|
| `schema_invalid` | 22 |
| `bq_dry_run_failed` | 14 |
| `ok` | 13 |
| `parse_error` | 1 |
