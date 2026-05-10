# Spider2-Lite-BQ v18 — `lite_bq_v21_pilot10`

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| plan_validation_ok | 5 | 50.0% |
| chosen_schema_valid | 4 | 40.0% |
| parse_ok | 10 | 100.0% |
| execute_ok (BQ dry_run) | 3 | 30.0% |
| chosen_family_A (deterministic) | 8 | 80.0% |
| chosen_family_B (Coder-7B direct) | 2 | 20.0% |

## Error taxonomy

| error_class | count |
|---|---:|
| `schema_invalid` | 6 |
| `bq_dry_run_failed` | 4 |
