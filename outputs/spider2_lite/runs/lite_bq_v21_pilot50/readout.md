# Spider2-Lite-BQ v18 — `lite_bq_v21_pilot50`

| metric | value | rate |
|---|---:|---:|
| n_total | 50 | — |
| plan_validation_ok | 27 | 54.0% |
| chosen_schema_valid | 25 | 50.0% |
| parse_ok | 49 | 98.0% |
| execute_ok (BQ dry_run) | 22 | 44.0% |
| chosen_family_A (deterministic) | 43 | 86.0% |
| chosen_family_B (Coder-7B direct) | 7 | 14.0% |

## Error taxonomy

| error_class | count |
|---|---:|
| `schema_invalid` | 24 |
| `bq_dry_run_failed` | 13 |
| `ok` | 12 |
| `parse_error` | 1 |
