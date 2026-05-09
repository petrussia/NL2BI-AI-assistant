# Spider2-Snow v9 — dialect fix + pilot10 diagnostics

_Generated: 2026-05-08 | dataset: CANONICAL Spider2-Snow 547_

## What v9 changed vs v8

1. **Backticks → unquoted SF identifier**: `\`a.b.c\`` → `B.C` (drop GCP project), or `A.B.C` uppercase.
2. **`UNNEST(arr)` → `LATERAL FLATTEN(input => arr) AS f`**.
3. **`SAFE_CAST` → `TRY_CAST`**.
4. **`DATE("YYYYMMDD")` → `TO_DATE('YYYYMMDD','YYYYMMDD')`**.
5. **`DATE_DIFF(d1, d2, DAY)` (BQ arg-order) → `DATEDIFF(DAY, d2, d1)` (SF)**.
6. **`DATE_TRUNC(d, PART)` → `DATE_TRUNC('PART', d)`**.
7. **`DATE_ADD(d, INTERVAL N PART)` → `DATEADD(PART, N, d)`**.
8. **`REGEXP_CONTAINS` → `REGEXP_LIKE`**.
9. **sqlglot transpile** as last-resort fallback for `[...]` brackets / `STRUCT(...)`.

Smoke-test verified all transforms produce expected output
(see `repo/src/evaluation/snowflake_dialect_normalizer_v9.py`).

## Pilot10 result (CANONICAL 547, limit=10, no-execute)

| metric | v8 pilot3 | **v9 pilot10** |
|---|---:|---:|
| n | 3 | 10 |
| parse_ok | 0/3 (0%) | **0/10 (0%)** |
| execute_ok | 0/3 (0%) | 0/10 (0%) |
| repair_helpful | 0 | 0 |
| dominant error | wrong_dialect (2), object_not_found (1) | **object_not_found (6), syntax (4)** |

Dialect-fix breakdown for v9 pilot10:

| fix | applied to N candidates |
|---|---:|
| `unnest_to_flatten` | 3 |

(other normalizer rules did not trigger because the model already
avoided most BQ-isms after the v8→v9 prompt update; remaining failures
are not dialect-shaped.)

## What changed in error mix v8 → v9

- **`wrong_dialect` disappears entirely.** v9 either auto-fixes the
  candidate (3× UNNEST→FLATTEN this run) or the model already produces
  acceptable Snowflake form. The dialect normalizer is doing its job.
- **New dominant errors are semantic, not lexical**:
  - `object_not_found` (6/10) — model invents column/table identifiers
    that look plausible but don't exist in the canonical Snow schema.
  - `syntax` (4/10) — usually one of:
    1. **Quadruple-qualified table** like
       `"GA4"."GA4_OBFUSCATED_SAMPLE_ECOMMERCE"."GA4_OBFUSCATED_SAMPLE_ECOMMERCE"."EVENTS_20201225"`
       (model concatenates schema name twice).
    2. **`LATERAL JOIN FLATTEN(...)`** instead of `CROSS JOIN LATERAL FLATTEN(...)`
       or `, LATERAL FLATTEN(...)`.
    3. **`event_params:engaged_session_event:int_value`** — VARIANT path
       to a non-existent inner field.

## Gate decision

Per the explicit user rule:
> Если pilot10 parse_ok не вырос хотя бы до 50%, FULL Snow не запускать.
> Сначала диагностировать.

**v9 pilot10 parse_ok = 0% << 50%. Snow FULL 547 NOT launched.**

## Root-cause hypotheses (next-session work)

| H | description | proposed remediation |
|---|---|---|
| H1 | Schema rendering shows BOTH `fq_name=DB.SCHEMA.TABLE` AND `table_fullname=SCHEMA.TABLE`; model concatenates | render only `fq_name`; drop `table_fullname` from prompt |
| H2 | Model invents columns because retrieval shortlist is wide and column descriptions are sparse for SF | switch to dense retrieval over column descriptions; reduce max_cols per table |
| H3 | Coder-7B does not have enough Snow-domain pre-training | upgrade to Coder-32B or a Snow-specific fine-tune |
| H4 | wall_time/task is high (66–227 s/task) for canonical Snow because schema rendering is large; this also truncates CTE candidate at max_new_cte=1100 | introduce per-task token budget cap + cheaper rendering |

## What's safe to claim from this run

- The v9 dialect normalizer **eliminated `wrong_dialect` failures**
  (2 → 0 in comparable error class).
- `object_not_found` remains the dominant blocker even after dialect
  fixes — this is a **schema-linking / model quality** problem, not a
  dialect problem.
- Spider2-Snow with Coder-7B + simple multi-candidate + retrieval is
  **not viable as-is** for a high-quality FULL run. Options listed
  under H1–H4 above.

## Artifacts

- Run dir: `outputs/spider2_snow/runs/snow_v9_pilot10/`
- Predictions: `outputs/predictions/spider2_snow_agent_v9_snow_v9_pilot10_predictions.jsonl`
- Per-candidate audit: `outputs/spider2_snow/runs/snow_v9_pilot10/candidates.jsonl`
- Trace + selector_audit + repair_record: `outputs/spider2_snow/runs/snow_v9_pilot10/traces.jsonl`
- Error taxonomy / source breakdown / dialect_fix_breakdown CSVs: same dir.
