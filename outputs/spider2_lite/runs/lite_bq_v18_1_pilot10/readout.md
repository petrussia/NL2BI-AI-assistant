# Spider2-Lite-BQ v18 — `lite_bq_v18_1_pilot10`

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| plan_validation_ok | 0 | 0.0% |
| chosen_schema_valid | 3 | 30.0% |
| parse_ok | 9 | 90.0% |
| execute_ok (BQ dry_run) | 1 | 10.0% |
| chosen_family_A (deterministic) | 6 | 60.0% |
| chosen_family_B (Coder-7B direct) | 4 | 40.0% |

## Error taxonomy

| error_class | count |
|---|---:|
| `schema_invalid` | 6 |
| `bq_dry_run_failed` | 3 |
| `parse_error` | 1 |
