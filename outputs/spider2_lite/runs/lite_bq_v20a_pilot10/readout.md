# Spider2-Lite-BQ v18 — `lite_bq_v20a_pilot10`

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| plan_validation_ok | 5 | 50.0% |
| chosen_schema_valid | 4 | 40.0% |
| parse_ok | 9 | 90.0% |
| execute_ok (BQ dry_run) | 3 | 30.0% |
| chosen_family_A (deterministic) | 7 | 70.0% |
| chosen_family_B (Coder-7B direct) | 3 | 30.0% |

## Error taxonomy

| error_class | count |
|---|---:|
| `schema_invalid` | 5 |
| `ok` | 2 |
| `bq_dry_run_failed` | 2 |
| `parse_error` | 1 |
