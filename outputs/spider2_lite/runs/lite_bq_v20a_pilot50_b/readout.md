# Spider2-Lite-BQ v18 — `lite_bq_v20a_pilot50_b`

| metric | value | rate |
|---|---:|---:|
| n_total | 50 | — |
| plan_validation_ok | 27 | 54.0% |
| chosen_schema_valid | 26 | 52.0% |
| parse_ok | 48 | 96.0% |
| execute_ok (BQ dry_run) | 21 | 42.0% |
| chosen_family_A (deterministic) | 41 | 82.0% |
| chosen_family_B (Coder-7B direct) | 9 | 18.0% |

## Error taxonomy

| error_class | count |
|---|---:|
| `schema_invalid` | 22 |
| `ok` | 15 |
| `bq_dry_run_failed` | 11 |
| `parse_error` | 2 |
