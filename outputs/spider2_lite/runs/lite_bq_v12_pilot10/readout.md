# Spider2-Lite-BQ v12 — run `lite_bq_v12_pilot10` (wildcard + struct-aware validator)

## Aggregate metrics

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| chosen_schema_valid | 1 | 10.0% |
| parse_ok | 0 | 0.0% |
| execute_ok | 0 | 0.0% |
| repair_helpful | 0 | — |
| struct_field_skips (FP avoided) | 68 | — |
| wildcard_table_resolves | 19 | — |

## Error taxonomy

| error_type | count |
|---|---:|
| `schema_invalid` | 9 |
| `BadRequest` | 1 |

## Source breakdown

| source | count |
|---|---:|
| `C0_direct` | 7 |
| `C1_retrieval` | 2 |
| `C2_cte` | 1 |