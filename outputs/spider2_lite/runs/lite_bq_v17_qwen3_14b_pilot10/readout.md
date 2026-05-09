# Spider2-Lite-BQ v16 — run `lite_bq_v17_qwen3_14b_pilot10` (constrained repair + nested rewrite)

## Aggregate metrics

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| chosen_schema_valid | 2 | 20.0% |
| parse_ok | 0 | 0.0% |
| execute_ok | 0 | 0.0% |
| constrained_repair_helpful | 2 | — |
| nested_rewrite_applied | 0 | — |
| struct_field_skips (FP avoided) | 104 | — |
| wildcard_resolves | 7 | — |

## Error taxonomy

| error_type | count |
|---|---:|
| `schema_invalid` | 8 |
| `BadRequest` | 2 |

## Source breakdown

| source | count |
|---|---:|
| `C0_direct` | 6 |
| `C1_retrieval` | 3 |
| `C2_cte` | 1 |