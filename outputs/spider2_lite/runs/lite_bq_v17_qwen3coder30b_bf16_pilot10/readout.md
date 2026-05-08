# Spider2-Lite-BQ v16 — run `lite_bq_v17_qwen3coder30b_bf16_pilot10` (constrained repair + nested rewrite)

## Aggregate metrics

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| chosen_schema_valid | 4 | 40.0% |
| parse_ok | 0 | 0.0% |
| execute_ok | 0 | 0.0% |
| constrained_repair_helpful | 3 | — |
| nested_rewrite_applied | 0 | — |
| struct_field_skips (FP avoided) | 72 | — |
| wildcard_resolves | 16 | — |

## Error taxonomy

| error_type | count |
|---|---:|
| `schema_invalid` | 6 |
| `object_not_found` | 4 |

## Source breakdown

| source | count |
|---|---:|
| `C0_direct` | 5 |
| `C2_cte` | 3 |
| `C1_retrieval` | 2 |