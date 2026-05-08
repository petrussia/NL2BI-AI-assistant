# Spider2-Lite-BQ v16 — run `lite_bq_v16_pilot10` (constrained repair + nested rewrite)

## Aggregate metrics

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| chosen_schema_valid | 6 | 60.0% |
| parse_ok | 0 | 0.0% |
| execute_ok | 0 | 0.0% |
| constrained_repair_helpful | 6 | — |
| nested_rewrite_applied | 0 | — |
| struct_field_skips (FP avoided) | 65 | — |
| wildcard_resolves | 17 | — |

## Error taxonomy

| error_type | count |
|---|---:|
| `object_not_found` | 5 |
| `schema_invalid` | 4 |
| `syntax` | 1 |

## Source breakdown

| source | count |
|---|---:|
| `C0_direct` | 5 |
| `C1_retrieval` | 3 |
| `C2_cte` | 2 |