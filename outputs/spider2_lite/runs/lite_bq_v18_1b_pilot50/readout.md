# Spider2-Lite-BQ v18 — `lite_bq_v18_1b_pilot50`

| metric | value | rate |
|---|---:|---:|
| n_total | 50 | — |
| plan_validation_ok | 21 | 42.0% |
| chosen_schema_valid | 26 | 52.0% |
| parse_ok | 48 | 96.0% |
| execute_ok (BQ dry_run) | 23 | 46.0% |
| chosen_family_A (deterministic) | 40 | 80.0% |
| chosen_family_B (Coder-7B direct) | 10 | 20.0% |

## Error taxonomy

| error_class | count |
|---|---:|
| `schema_invalid` | 22 |
| `ok` | 17 |
| `bq_dry_run_failed` | 9 |
| `parse_error` | 2 |
