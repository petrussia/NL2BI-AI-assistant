# Spider2-Snow v10 — H1 identifier rendering fix

_Generated: 2026-05-08 | branch experiments/denis_

## Problem (v9 pilot10)

Coder-7B emitted 4-part fully-quoted identifiers like:

```
"GA4"."GA4_OBFUSCATED_SAMPLE_ECOMMERCE"."GA4_OBFUSCATED_SAMPLE_ECOMMERCE"."EVENTS_20201225"
```

— a duplicated middle segment, plus per-segment quoting that the
canonical schema didn't show. Snowflake responded with `syntax` /
`object_not_found`. v9 pilot10 had 0/10 parse_ok.

## Root cause

`spider2_sf_schema_index_v8.render_table_block` rendered the table
header as `f'"{t.fq_name}"'` — a **single pair of quotes wrapping the
whole 3-part name** (`"DB.SCHEMA.TABLE"`). The model interpreted that
as one quoted identifier, then in its output rebuilt it
component-by-component but lost track of the schema vs database
distinction, producing a 4-part with a duplicated segment.

## v10 fix (this session)

`repo/src/evaluation/spider2_snow_schema_render_v10.py`:

1. **Render table header** as the canonical unquoted 3-part form
   `DB.SCHEMA.TABLE` — no outer quotes, no `table_fullname` field.
2. **Strict prompt rule** in `spider2_snow_prompting_v10`:
   - 3-part identifiers ONLY (DB.SCHEMA.TABLE).
   - Never repeat any segment.
   - Never wrap multi-part identifier in a single pair of quotes.
   - Use only identifiers from the SCHEMA block.
3. **Identifier post-normalizer** `normalize_identifiers_v10(sql)`:
   - `A.B.B.C` (4-part with B repeated) → `A.B.C`. Handles
     per-segment quoting `"A"."B"."B"."C"` as well.
   - `"DB.SCHEMA.TABLE"` (whole-blob single-quoted) → `DB.SCHEMA.TABLE`.

## Smoke-test (deterministic)

| input | applied fix | output |
|---|---|---|
| `"GA4"."X"."X"."T"` | `4part_collapsed` | `GA4.X.T` |
| `"DB.SCHEMA.TABLE"` | `quoted_blob_unwrapped` | `DB.SCHEMA.TABLE` |
| `A.B.B.C` | `4part_collapsed` | `A.B.C` |
| `PATENTS.PUBLIC.PUBLICATIONS` | (none, already canonical) | `PATENTS.PUBLIC.PUBLICATIONS` |

## Pilot10 result (`outputs/spider2_snow/runs/snow_v10_pilot10/`)

| metric | v9 | **v10** |
|---|---:|---:|
| n | 10 | 10 |
| parse_ok | 0 (0%) | **0 (0%)** |
| identifier_4part_collapsed (across all candidates) | n/a | **58** |
| identifier_quoted_blob_unwrapped | n/a | 0 |
| `wrong_dialect` errors | 0 | 0 |
| `object_not_found` | 6 | 7 |
| `syntax` | 4 | 3 |

## Conclusion

The H1 fix is necessary AND working — it collapses every 4-part
artifact the model produced (58 cases across 10 tasks). But it is
**not sufficient** to lift parse_ok above 0%. After identifier
hygiene, the dominant error class is `object_not_found` (model invents
columns / tables that aren't in the canonical Snow schema). That is a
**schema-linking + model quality** problem, not a rendering problem.

Per gate policy (≥50% for FULL launch), Spider2-Snow FULL 547 stays
deferred. Next levers in priority order:

1. **Retrieval rework** — give the model exact column lists for
   shortlisted tables, capped by token budget; deterministic ordering.
2. **Stronger generator** — INT4-quantized Coder-32B (Coder-32B BF16
   is ~64 GB and won't fit Colab L4 22 GB).
3. **Fewer, more focused candidates** — three candidates competing for
   the same prompt budget produce variations on the same wrong shape;
   one well-grounded candidate may outperform.

## Examples table

See `outputs/tables/spider2_snow_identifier_fix_examples_v10.csv` for
per-candidate before/after SQL excerpts (only available when the agent
records both `original_sql` and final normalized form, which v10 does).
