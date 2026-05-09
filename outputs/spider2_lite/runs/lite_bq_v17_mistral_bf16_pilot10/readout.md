# Spider2-Lite-BQ v16 — run `lite_bq_v17_mistral_bf16_pilot10` (constrained repair + nested rewrite)

## Aggregate metrics

| metric | value | rate |
|---|---:|---:|
| n_total | 10 | — |
| chosen_schema_valid | 3 | 30.0% |
| parse_ok | 0 | 0.0% |
| execute_ok | 0 | 0.0% |
| constrained_repair_helpful | 3 | — |
| nested_rewrite_applied | 0 | — |
| struct_field_skips (FP avoided) | 29 | — |
| wildcard_resolves | 6 | — |

## Error taxonomy

| error_type | count |
|---|---:|
| `schema_invalid` | 7 |
| `BadRequest` | 2 |
| `object_not_found` | 1 |

## Source breakdown

| source | count |
|---|---:|
| `C0_direct` | 5 |
| `C1_retrieval` | 4 |
| `C2_cte` | 1 |